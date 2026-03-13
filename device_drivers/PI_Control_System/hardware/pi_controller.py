"""
PI GCS implementation for axis control.

Wraps pipython GCSDevice for single-axis operations.
Source: legacy/PI_Control_GUI/hardware_controller.py
"""

import time
from typing import Optional

from pipython import GCSDevice, pitools

from ..core.hardware.interfaces import AxisController
from ..core.models import Axis, AxisConfig
from ..core.errors import (
    ConnectionError,
    InitializationError,
    MotionError,
    CommunicationError
)


class PIAxisController(AxisController):
    """PI GCS implementation for single axis control.

    Wraps one GCSDevice instance for one physical axis.
    Source: legacy/PI_Control_GUI/hardware_controller.py
    """

    def __init__(self, config: AxisConfig):
        """Initialize controller with configuration.

        Args:
            config: Axis configuration
        """
        self._config = config
        self._device: Optional[GCSDevice] = None
        self._connected = False
        self._initialized = False

    @property
    def axis(self) -> Axis:
        return self._config.axis

    @property
    def config(self) -> AxisConfig:
        return self._config

    @property
    def is_connected(self) -> bool:
        return self._connected

    @property
    def is_initialized(self) -> bool:
        return self._initialized

    def connect(self) -> None:
        """Connect via USB using serial number.

        Source: legacy/PI_Control_GUI/hardware_controller.py:35-57
        """
        if self._connected:
            return

        try:
            self._device = GCSDevice()
            self._device.ConnectUSB(serialnum=self._config.serial)
            idn = self._device.qIDN().strip()
            self._connected = True
            print(f"[{self._config.axis.value}] Connected: {idn}")

        except Exception as e:
            self._device = None
            raise ConnectionError(
                f"Failed to connect to {self._config.axis.value} "
                f"(S/N {self._config.serial}): {e}"
            ) from e

    def disconnect(self) -> None:
        """Close connection and cleanup.

        Source: legacy/PI_Control_GUI/hardware_controller.py:330-346
        """
        if self._device and self._device.IsConnected():
            try:
                self._device.CloseConnection()
                print(f"[{self._config.axis.value}] Disconnected")
            except Exception as e:
                print(f"[{self._config.axis.value}] Disconnect error: {e}")

        self._device = None
        self._connected = False
        self._initialized = False

    def initialize(self) -> None:
        """Initialize and reference axis.

        Source: legacy/PI_Control_GUI/hardware_controller.py:71-104
        Source: legacy/Tmotion2.0.py:60-73
        """
        if not self._connected:
            raise InitializationError(f"{self._config.axis.value}: Not connected")

        if self._initialized:
            return

        try:
            ax = self._device.axes[0]

            print(f"[{self._config.axis.value}] Initializing stage...")

            # 1. Check current stage configuration
            current_stage = self._device.qCST().get(ax, '')
            if current_stage != self._config.stage:
                # Only configure if different
                print(f"[{self._config.axis.value}]   - Configuring stage '{self._config.stage}'...")
                try:
                    self._device.CST(ax, self._config.stage)
                    time.sleep(0.1)
                except Exception as e:
                    # Stage database error - check if already configured correctly
                    current_stage = self._device.qCST().get(ax, '')
                    if current_stage == self._config.stage:
                        print(f"[{self._config.axis.value}]   - Stage already configured (database unavailable)")
                    else:
                        raise e
            else:
                print(f"[{self._config.axis.value}]   - Stage already configured as '{self._config.stage}'")

            # 2. Enable servo
            print(f"[{self._config.axis.value}]   - Enabling servo...")
            self._device.SVO(ax, True)

            # 3. Execute reference move
            print(f"[{self._config.axis.value}]   - Starting referencing move ('{self._config.refmode}')...")
            ref_command = getattr(self._device, self._config.refmode)
            ref_command(ax)
            pitools.waitontarget(self._device)

            # 4. Move slightly off limit switch
            print(f"[{self._config.axis.value}]   - Moving off limit switch...")
            self._device.MVR(ax, -0.1)
            pitools.waitontarget(self._device)

            # 5. Set max velocity for initialization
            print(f"[{self._config.axis.value}]   - Setting max velocity...")
            self._device.VEL(ax, self._config.max_velocity)

            pos = self._device.qPOS(ax)[ax]
            print(f"[{self._config.axis.value}] Initialized. Position: {pos:.3f} mm")

            self._initialized = True

        except Exception as e:
            raise InitializationError(
                f"Failed to initialize {self._config.axis.value}: {e}"
            ) from e

    def move_absolute(self, position: float) -> None:
        """MOV command with range clamping.

        Source: legacy/PI_Control_GUI/hardware_controller.py:152-175
        """
        self._check_initialized()

        # Clamp to safe range
        clamped = self._config.range.clamp(position)
        if clamped != position:
            print(f"[{self._config.axis.value}] Position {position:.3f} clamped to {clamped:.3f}")

        try:
            ax = self._device.axes[0]
            self._device.MOV(ax, clamped)

        except Exception as e:
            raise MotionError(
                f"Move failed for {self._config.axis.value} to {clamped:.3f}: {e}"
            ) from e

    def move_relative(self, distance: float) -> None:
        """MVR command with range clamping.

        Source: legacy/PI_Control_GUI/hardware_controller.py:177-205
        """
        self._check_initialized()

        # Calculate target and clamp
        current = self.get_position()
        target = current + distance
        clamped = self._config.range.clamp(target)
        actual_distance = clamped - current

        if actual_distance != distance:
            print(f"[{self._config.axis.value}] Distance {distance:.3f} adjusted to {actual_distance:.3f}")

        try:
            ax = self._device.axes[0]
            self._device.MVR(ax, actual_distance)

        except Exception as e:
            raise MotionError(
                f"Relative move failed for {self._config.axis.value}: {e}"
            ) from e

    def get_position(self) -> float:
        """Query position with qPOS.

        Source: legacy/PI_Control_GUI/hardware_controller.py:225-243
        """
        self._check_initialized()

        try:
            ax = self._device.axes[0]
            return self._device.qPOS(ax)[ax]

        except Exception as e:
            raise CommunicationError(
                f"Position query failed for {self._config.axis.value}: {e}"
            ) from e

    def set_velocity(self, velocity: float) -> None:
        """Set velocity with VEL command.

        Source: legacy/PI_Control_GUI/hardware_controller.py:122-150
        """
        self._check_initialized()

        # Clamp to max
        clamped = min(velocity, self._config.max_velocity)
        if clamped != velocity:
            print(f"[{self._config.axis.value}] Velocity {velocity:.2f} clamped to {clamped:.2f}")

        try:
            ax = self._device.axes[0]
            self._device.VEL(ax, clamped)

        except Exception as e:
            raise CommunicationError(
                f"Velocity set failed for {self._config.axis.value}: {e}"
            ) from e

    def stop(self) -> None:
        """Emergency stop with STP.

        Source: legacy/PI_Control_GUI/hardware_controller.py:274-286
        """
        if self._connected and self._device:
            try:
                self._device.STP()
                print(f"[{self._config.axis.value}] Emergency stop")
            except Exception as e:
                print(f"[{self._config.axis.value}] Stop error: {e}")

    def is_on_target(self) -> bool:
        """Check qONT status.

        Source: legacy/PI_Control_GUI/hardware_controller.py:256-272
        """
        if not self._initialized:
            return False

        try:
            ax = self._device.axes[0]
            return self._device.qONT(ax)[ax]

        except Exception:
            return False

    def wait_for_target(self, timeout: Optional[float] = None) -> None:
        """Block until on target.

        Source: legacy/PI_Control_GUI/hardware_controller.py:207-223
        Uses pipython.pitools.waitontarget()
        """
        self._check_initialized()

        try:
            # pipython requires numeric timeout, default to 60s if None
            actual_timeout = timeout if timeout is not None else 60.0
            pitools.waitontarget(self._device, timeout=actual_timeout)

        except Exception as e:
            raise MotionError(
                f"Wait for target failed on {self._config.axis.value}: {e}"
            ) from e

    def _check_initialized(self) -> None:
        """Raise if not initialized."""
        if not self._initialized:
            raise InitializationError(
                f"Axis {self._config.axis.value} not initialized"
            )
