"""
Manual test script for MainWindow assembly.

Run this script to visually verify:
- MainWindow renders with all panels
- Connection workflow: Connect → Initialize → Ready
- Position display updates during motion
- Manual jog buttons work
- System log shows all events
- Disconnect clears state

Usage:
    python -m PI_Control_System.tests.manual_test_main_window
"""

import sys
from PySide6.QtWidgets import QApplication

from PI_Control_System.core.models import Axis
from PI_Control_System.services.event_bus import EventBus
from PI_Control_System.services.connection_service import ConnectionService
from PI_Control_System.services.motion_service import MotionService
from PI_Control_System.hardware.pi_manager import PIControllerManager
from PI_Control_System.hardware.mock_controller import MockAxisController
from PI_Control_System.config.loader import load_config
from PI_Control_System.gui.main_window import MainWindow


def create_mock_manager():
    """Create PIControllerManager with mock controllers for testing."""
    config = load_config()

    # MockAxisController takes AxisConfig directly
    mock_controllers = {
        Axis.X: MockAxisController(config.axis_configs[Axis.X]),
        Axis.Y: MockAxisController(config.axis_configs[Axis.Y]),
        Axis.Z: MockAxisController(config.axis_configs[Axis.Z]),
    }

    # PIControllerManager only accepts controllers dict
    return PIControllerManager(controllers=mock_controllers)


def main():
    """Launch MainWindow with mock hardware."""
    app = QApplication(sys.argv)

    # Load config
    config = load_config()

    # Create services with correct signatures
    event_bus = EventBus()
    manager = create_mock_manager()

    # ConnectionService(manager, event_bus, executor=None)
    from concurrent.futures import ThreadPoolExecutor
    executor = ThreadPoolExecutor(max_workers=4)
    connection_service = ConnectionService(manager, event_bus, executor)

    # MotionService(controller_manager, event_bus, executor, connection_service)
    motion_service = MotionService(
        controller_manager=manager,
        event_bus=event_bus,
        executor=executor,
        connection_service=connection_service
    )

    # Create and show main window
    window = MainWindow(
        event_bus=event_bus,
        connection_service=connection_service,
        motion_service=motion_service
    )
    window.show()

    print("=" * 60)
    print("Manual Test Instructions:")
    print("=" * 60)
    print("1. Click 'Connect' button")
    print("   -> Status should show 'Connecting...' then 'Connected'")
    print("   -> System log should show connection messages")
    print()
    print("2. Click 'Initialize' button")
    print("   -> Status should show 'Initializing...' then 'Ready'")
    print("   -> System log should show referencing progress")
    print("   -> Position display should show current positions")
    print("   -> Velocity controls should become enabled")
    print("   -> Jog buttons should become enabled")
    print()
    print("3. Test manual jog:")
    print("   -> Click '+X' or '-X' buttons")
    print("   -> Position should update in real-time")
    print("   -> System log should show motion events")
    print()
    print("4. Adjust velocity:")
    print("   -> Move velocity sliders or change spinbox values")
    print("   -> System log should show velocity change messages")
    print()
    print("5. Click 'Disconnect'")
    print("   -> Status should show 'Disconnected'")
    print("   -> Position display should clear (show '---')")
    print("   -> Controls should become disabled")
    print()
    print("6. Verify system log preserves all messages")
    print("   -> Scroll through log to see full event history")
    print()
    print("=" * 60)

    sys.exit(app.exec())


if __name__ == '__main__':
    main()
