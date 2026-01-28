"""
Abstract hardware interfaces for axis control.

Defines contracts that both real PI hardware and mock implementations must follow.
Source: legacy/PI_Control_GUI/hardware_controller.py
"""

from abc import ABC, abstractmethod
from typing import Optional

from ..models import Axis, AxisConfig, Position


class AxisController(ABC):
    """Abstract interface for single-axis controller.

    Responsibilities:
    - Connection lifecycle (connect/disconnect)
    - Initialization and referencing
    - Motion commands (absolute, relative)
    - Position queries
    - Velocity management
    - Emergency stop

    Source: legacy/PI_Control_GUI/hardware_controller.py:35-247
    """

    @property
    @abstractmethod
    def axis(self) -> Axis:
        """Axis identifier."""
        pass

    @property
    @abstractmethod
    def config(self) -> AxisConfig:
        """Axis configuration."""
        pass

    @property
    @abstractmethod
    def is_connected(self) -> bool:
        """Connection status."""
        pass

    @property
    @abstractmethod
    def is_initialized(self) -> bool:
        """Initialization/reference status."""
        pass

    @abstractmethod
    def connect(self) -> None:
        """Establish connection to hardware.

        Raises:
            ConnectionError: If connection fails

        Source: legacy/PI_Control_GUI/hardware_controller.py:35-57
        """
        pass

    @abstractmethod
    def disconnect(self) -> None:
        """Close connection and cleanup resources.

        Source: legacy/PI_Control_GUI/hardware_controller.py:330-346
        """
        pass

    @abstractmethod
    def initialize(self) -> None:
        """Initialize and reference the axis.

        Performs full initialization sequence:
        1. Configure stage type (CST)
        2. Enable servo (SVO)
        3. Execute reference move (FPL/FNL/etc)
        4. Move off limit switch
        5. Set default velocity

        Raises:
            InitializationError: If initialization fails

        Source: legacy/PI_Control_GUI/hardware_controller.py:71-104
        """
        pass

    @abstractmethod
    def move_absolute(self, position: float) -> None:
        """Move to absolute position (MOV command).

        Position is clamped to safe range by implementation.

        Args:
            position: Target position in mm (unclamped)

        Raises:
            MotionError: If move command fails
            InitializationError: If not initialized

        Source: legacy/PI_Control_GUI/hardware_controller.py:152-175
        """
        pass

    @abstractmethod
    def move_relative(self, distance: float) -> None:
        """Move relative distance (MVR command).

        Final position is clamped to safe range by implementation.

        Args:
            distance: Distance in mm (positive or negative)

        Raises:
            MotionError: If move command fails
            InitializationError: If not initialized

        Source: legacy/PI_Control_GUI/hardware_controller.py:177-205
        """
        pass

    @abstractmethod
    def get_position(self) -> float:
        """Query current position (qPOS).

        Returns:
            Current position in mm

        Raises:
            CommunicationError: If query fails

        Source: legacy/PI_Control_GUI/hardware_controller.py:225-243
        """
        pass

    @abstractmethod
    def set_velocity(self, velocity: float) -> None:
        """Set motion velocity (VEL command).

        Velocity is clamped to max_velocity from config.

        Args:
            velocity: Velocity in mm/s

        Raises:
            CommunicationError: If command fails

        Source: legacy/PI_Control_GUI/hardware_controller.py:122-150
        """
        pass

    @abstractmethod
    def stop(self) -> None:
        """Emergency stop (STP command).

        Best-effort stop, should not raise exceptions.

        Source: legacy/PI_Control_GUI/hardware_controller.py:274-286
        """
        pass

    @abstractmethod
    def is_on_target(self) -> bool:
        """Check if axis reached target (qONT).

        Returns:
            True if on target, False if moving

        Source: legacy/PI_Control_GUI/hardware_controller.py:256-272
        """
        pass

    @abstractmethod
    def wait_for_target(self, timeout: Optional[float] = None) -> None:
        """Block until axis reaches target.

        Args:
            timeout: Maximum wait time in seconds (None = infinite)

        Raises:
            TimeoutError: If timeout exceeded
            MotionError: If motion fails

        Source: legacy/PI_Control_GUI/hardware_controller.py:207-223
        Uses pipython.pitools.waitontarget()
        """
        pass


class AxisControllerManager(ABC):
    """Abstract interface for managing multiple axis controllers.

    Responsibilities:
    - Multi-axis connection/initialization coordination
    - Safe reference ordering (Z → X → Y)
    - Park sequence (Z first, then X/Y together)
    - Position snapshot retrieval

    Source: legacy/PI_Control_GUI/hardware_controller.py (multi-axis operations)
    Source: legacy/origintools.py:42-96 (park sequence)
    """

    @abstractmethod
    def connect_all(self) -> None:
        """Connect to all axis controllers.

        Raises:
            ConnectionError: If any connection fails

        Source: legacy/PI_Control_GUI/hardware_controller.py:35-57
        """
        pass

    @abstractmethod
    def disconnect_all(self) -> None:
        """Disconnect all controllers.

        Best-effort cleanup, should not raise.

        Source: legacy/PI_Control_GUI/hardware_controller.py:330-346
        """
        pass

    @abstractmethod
    def initialize_all(self) -> None:
        """Initialize and reference all axes in safe order.

        Order: Z → X → Y (Z first for safety)

        Raises:
            InitializationError: If any initialization fails

        Source: legacy/PI_Control_GUI/hardware_controller.py:59-120
        Source: legacy/PI_Control_GUI/config.py:34 (REFERENCE_ORDER)
        """
        pass

    @abstractmethod
    def get_controller(self, axis: Axis) -> AxisController:
        """Get controller for specific axis.

        Args:
            axis: Axis identifier

        Returns:
            AxisController instance

        Raises:
            KeyError: If axis not found
        """
        pass

    @abstractmethod
    def get_position_snapshot(self) -> Position:
        """Query current position of all axes.

        Returns:
            Position with all axis coordinates

        Source: legacy/PI_Control_GUI/hardware_controller.py:245-254
        """
        pass

    @abstractmethod
    def park_all(self, position: float) -> None:
        """Park all axes safely.

        Safe sequence:
        1. Move Z to park position, wait
        2. Move X and Y simultaneously to park position
        3. Wait for X and Y

        Args:
            position: Park coordinate in mm

        Raises:
            MotionError: If park fails

        Source: legacy/origintools.py:42-96 (reset function)
        Source: legacy/PI_Control_GUI/hardware_controller.py:288-328
        """
        pass
