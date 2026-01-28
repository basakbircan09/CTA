"""
Application factory for dependency injection.

Responsibilities:
- Load configuration
- Create shared thread pool executor
- Instantiate hardware manager
- Wire services with shared dependencies
- Create and return MainWindow

Source: Phase 6 Task 6.1 specification
"""

from concurrent.futures import ThreadPoolExecutor
from typing import Optional

from PySide6.QtWidgets import QApplication

from .config.loader import load_config
from .core.models import Axis
from .hardware.pi_manager import PIControllerManager
from .services.event_bus import EventBus
from .services.connection_service import ConnectionService
from .services.motion_service import MotionService
from .gui.main_window import MainWindow


def create_app(use_mock: bool = False) -> MainWindow:
    """Create and wire application components.

    All services share:
    - Single ThreadPoolExecutor instance
    - ConfigBundle from loader
    - EventBus instance

    Args:
        use_mock: If True, use MockAxisController instead of real hardware

    Returns:
        Configured MainWindow instance ready to show()
    """
    # Load configuration
    config = load_config()

    # Shared executor for all async operations
    executor = ThreadPoolExecutor(max_workers=4, thread_name_prefix="PIControl")

    # Create event bus
    event_bus = EventBus()

    # Create hardware manager
    if use_mock:
        from .hardware.mock_controller import MockAxisController
        controllers = {
            Axis.X: MockAxisController(config.axis_configs[Axis.X]),
            Axis.Y: MockAxisController(config.axis_configs[Axis.Y]),
            Axis.Z: MockAxisController(config.axis_configs[Axis.Z]),
        }
    else:
        # Import PIAxisController only when needed (requires pipython + hardware DLLs)
        from .hardware.pi_controller import PIAxisController
        controllers = {
            Axis.X: PIAxisController(config.axis_configs[Axis.X]),
            Axis.Y: PIAxisController(config.axis_configs[Axis.Y]),
            Axis.Z: PIAxisController(config.axis_configs[Axis.Z]),
        }

    manager = PIControllerManager(controllers=controllers)

    # Wire services with shared dependencies
    connection_service = ConnectionService(
        manager=manager,
        event_bus=event_bus,
        executor=executor
    )

    motion_service = MotionService(
        controller_manager=manager,
        event_bus=event_bus,
        executor=executor,
        connection_service=connection_service
    )

    # Create main window
    window = MainWindow(
        event_bus=event_bus,
        connection_service=connection_service,
        motion_service=motion_service,
        park_position=config.park_position
    )

    return window


def run_app(use_mock: bool = False, app: Optional[QApplication] = None) -> int:
    """Run the application.

    Args:
        use_mock: If True, use mock hardware
        app: QApplication instance (creates new if None)

    Returns:
        Application exit code
    """
    if app is None:
        import sys
        app = QApplication(sys.argv)

    window = create_app(use_mock=use_mock)
    window.show()

    return app.exec()
