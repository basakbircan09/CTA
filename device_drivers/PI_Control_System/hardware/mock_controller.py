"""
Mock axis controller for deterministic testing.

Provides fake hardware implementation for unit tests without real PI hardware.
"""

import time
from typing import Optional

from ..core.hardware.interfaces import AxisController
from ..core.models import Axis, AxisConfig
from ..core.errors import (
    ConnectionError,
    InitializationError,
    MotionError,
    CommunicationError
)


class MockAxisController(AxisController):
    """Mock implementation for testing.

    Simulates axis behavior without real hardware:
    - Tracks connection/initialization state
    - Simulates position changes
    - Validates operation order
    - Controllable delays for motion simulation
    """

    def __init__(self, config: AxisConfig, fail_on_connect: bool = False,
                 fail_on_initialize: bool = False, motion_delay: float = 0.0):
        """Initialize mock controller.

        Args:
            config: Axis configuration
            fail_on_connect: If True, connect() raises ConnectionError
            fail_on_initialize: If True, initialize() raises InitializationError
            motion_delay: Simulated motion time in seconds
        """
        self._config = config
        self._connected = False
        self._initialized = False
        self._position = 0.0
        self._velocity = config.default_velocity
        self._moving = False
        self._target_position: Optional[float] = None

        # Test control flags
        self._fail_on_connect = fail_on_connect
        self._fail_on_initialize = fail_on_initialize
        self._motion_delay = motion_delay

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
        """Simulate connection."""
        if self._fail_on_connect:
            raise ConnectionError(f"Mock connection failure for {self._config.axis.value}")

        self._connected = True

    def disconnect(self) -> None:
        """Simulate disconnection."""
        self._connected = False
        self._initialized = False
        self._moving = False
        self._target_position = None

    def initialize(self) -> None:
        """Simulate initialization."""
        if not self._connected:
            raise InitializationError(f"{self._config.axis.value}: Not connected")

        if self._fail_on_initialize:
            raise InitializationError(f"Mock initialization failure for {self._config.axis.value}")

        # Simulate reference move - set position to range min
        self._position = self._config.range.min
        self._velocity = self._config.default_velocity
        self._initialized = True

    def move_absolute(self, position: float) -> None:
        """Simulate absolute move."""
        self._check_initialized()

        # Clamp to range
        clamped = self._config.range.clamp(position)

        # Start simulated move
        self._target_position = clamped
        self._moving = True

    def move_relative(self, distance: float) -> None:
        """Simulate relative move."""
        self._check_initialized()

        # Calculate target and clamp
        target = self._position + distance
        clamped = self._config.range.clamp(target)

        # Start simulated move
        self._target_position = clamped
        self._moving = True

    def get_position(self) -> float:
        """Return current position."""
        self._check_initialized()
        return self._position

    def set_velocity(self, velocity: float) -> None:
        """Set velocity (clamped to max)."""
        self._check_initialized()
        self._velocity = min(velocity, self._config.max_velocity)

    def stop(self) -> None:
        """Stop motion."""
        self._moving = False
        self._target_position = None

    def is_on_target(self) -> bool:
        """Check if on target."""
        if not self._initialized:
            return False

        return not self._moving and self._target_position is None

    def wait_for_target(self, timeout: Optional[float] = None) -> None:
        """Block until on target."""
        self._check_initialized()

        if not self._moving:
            return

        # Simulate motion delay
        if self._motion_delay > 0:
            time.sleep(self._motion_delay)

        # Complete the move
        if self._target_position is not None:
            self._position = self._target_position
            self._target_position = None

        self._moving = False

    def _check_initialized(self) -> None:
        """Raise if not initialized."""
        if not self._initialized:
            raise InitializationError(
                f"Axis {self._config.axis.value} not initialized"
            )
