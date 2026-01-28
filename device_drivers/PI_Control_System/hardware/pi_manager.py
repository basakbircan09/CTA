"""
PI controller manager for multi-axis coordination.

Manages three PIAxisController instances and coordinates multi-axis operations.
Source: legacy/PI_Control_GUI/hardware_controller.py (multi-axis operations)
Source: legacy/origintools.py (park sequence)
"""

from ..core.hardware.interfaces import AxisController, AxisControllerManager
from ..core.models import Axis, AxisConfig, Position
from ..core.errors import ConnectionError, InitializationError, MotionError


# Safe reference order: Z first for safety
# Source: legacy/PI_Control_GUI/config.py:34
REFERENCE_ORDER = [Axis.Z, Axis.X, Axis.Y]


class PIControllerManager(AxisControllerManager):
    """Manages three axis controllers.

    Responsibilities:
    - Coordinate connection/initialization for all axes
    - Enforce safe reference order (Z → X → Y)
    - Execute safe park sequence (Z first, then X/Y together)
    - Provide position snapshots

    Source: legacy/PI_Control_GUI/hardware_controller.py

    Design: Accepts AxisController instances (dependency injection) to enable
    testing with mocks without requiring real hardware.
    """

    def __init__(self, controllers: dict[Axis, AxisController]):
        """Initialize manager with controller instances.

        Args:
            controllers: Dict mapping Axis to AxisController instances
                        (can be PIAxisController or MockAxisController)

        Raises:
            ValueError: If any required axis is missing
        """
        self._controllers = controllers

        # Validate all required axes present
        for axis in [Axis.X, Axis.Y, Axis.Z]:
            if axis not in controllers:
                raise ValueError(f"Missing controller for {axis.value}")

    def connect_all(self) -> None:
        """Connect to all axis controllers.

        Source: legacy/PI_Control_GUI/hardware_controller.py:35-57
        """
        print("=== Connecting to all controllers ===")

        try:
            for axis in [Axis.X, Axis.Y, Axis.Z]:
                self._controllers[axis].connect()

            print("All controllers connected successfully\n")

        except Exception as e:
            # Cleanup partial connections
            print(f"Connection failed: {e}")
            self.disconnect_all()
            raise ConnectionError(f"Failed to connect all controllers: {e}") from e

    def disconnect_all(self) -> None:
        """Disconnect all controllers.

        Source: legacy/PI_Control_GUI/hardware_controller.py:330-346
        """
        print("\n=== Closing all connections ===")

        for axis, controller in self._controllers.items():
            try:
                controller.disconnect()
            except Exception as e:
                print(f"Error disconnecting {axis.value}: {e}")

        print("All connections closed\n")

    def initialize_all(self) -> None:
        """Initialize and reference all axes in safe order.

        Order: Z → X → Y (Z first for safety)

        Source: legacy/PI_Control_GUI/hardware_controller.py:59-120
        Source: legacy/PI_Control_GUI/config.py:34 (REFERENCE_ORDER)
        Source: legacy/Tmotion2.0.py:28
        """
        print("=== Initializing and referencing all stages ===")
        print(f"Reference order: {' -> '.join(ax.value for ax in REFERENCE_ORDER)}\n")

        try:
            for axis in REFERENCE_ORDER:
                self._controllers[axis].initialize()

            print("All stages initialized and ready\n")

        except Exception as e:
            raise InitializationError(f"Initialization failed: {e}") from e

    def get_controller(self, axis: Axis) -> AxisController:
        """Get controller for specific axis.

        Args:
            axis: Axis identifier

        Returns:
            AxisController instance

        Raises:
            KeyError: If axis not found
        """
        if axis not in self._controllers:
            raise KeyError(f"No controller for {axis.value}")
        return self._controllers[axis]

    def get_position_snapshot(self) -> Position:
        """Query current position of all axes.

        Returns:
            Position with all axis coordinates

        Source: legacy/PI_Control_GUI/hardware_controller.py:245-254
        """
        return Position(
            x=self._controllers[Axis.X].get_position(),
            y=self._controllers[Axis.Y].get_position(),
            z=self._controllers[Axis.Z].get_position()
        )

    def park_all(self, position: float) -> None:
        """Park all axes safely.

        Safe sequence:
        1. Move Z to park position, wait
        2. Move X and Y simultaneously to park position
        3. Wait for X and Y

        Args:
            position: Park coordinate in mm

        Source: legacy/origintools.py:42-96 (reset function)
        Source: legacy/PI_Control_GUI/hardware_controller.py:288-328
        """
        print(f"\n=== Starting Park Sequence: Moving all axes to {position} mm ===")

        try:
            # Set all axes to max velocity for parking
            print("  - Setting max velocity for all axes...")
            for controller in self._controllers.values():
                controller.set_velocity(controller.config.max_velocity)

            # Step 1: Park Z first (safety)
            print("  - Moving Z-axis to park position...")
            z_controller = self._controllers[Axis.Z]
            z_controller.move_absolute(position)
            z_controller.wait_for_target()
            print("  - Axis Z is parked")

            # Step 2: Park X and Y simultaneously (efficiency)
            print("  - Commanding X and Y axes to park position...")
            x_controller = self._controllers[Axis.X]
            y_controller = self._controllers[Axis.Y]

            x_controller.move_absolute(position)
            y_controller.move_absolute(position)

            print("  - Waiting for X and Y to park...")
            x_controller.wait_for_target()
            print("  - Axis X is parked")

            y_controller.wait_for_target()
            print("  - Axis Y is parked")

            print("\n=== Park Sequence Finished ===\n")

        except Exception as e:
            raise MotionError(f"Park sequence failed: {e}") from e


def create_pi_manager(configs: dict[Axis, AxisConfig]) -> PIControllerManager:
    """Factory function to create PIControllerManager with real PI hardware.

    Args:
        configs: Dict mapping Axis to AxisConfig

    Returns:
        PIControllerManager with PIAxisController instances

    Example:
        >>> from PI_Control_System.config import load_config
        >>> bundle = load_config()
        >>> manager = create_pi_manager(bundle.axis_configs)
        >>> manager.connect_all()
    """
    from .pi_controller import PIAxisController

    controllers = {
        axis: PIAxisController(config)
        for axis, config in configs.items()
    }

    return PIControllerManager(controllers)
