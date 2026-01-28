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


def create_services(use_mock: bool = False):
    """
    Create core PI services (no GUI).

    Returns:
        event_bus, connection_service, motion_service
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
        executor=executor,
    )

    motion_service = MotionService(
        controller_manager=manager,
        event_bus=event_bus,
        executor=executor,
        connection_service=connection_service,
    )

    # Also return config if you ever need park_position externally
    return event_bus, connection_service, motion_service, config


def create_app(use_mock: bool = False) -> MainWindow:
    """Create and wire application components and GUI MainWindow."""
    event_bus, connection_service, motion_service, config = create_services(use_mock=use_mock)

    window = MainWindow(
        event_bus=event_bus,
        connection_service=connection_service,
        motion_service=motion_service,
        park_position=config.park_position,
    )
    return window


def run_app(use_mock: bool = False, app: Optional[QApplication] = None) -> int:
    """Run the full PI GUI application."""
    if app is None:
        import sys
        app = QApplication(sys.argv)

    window = create_app(use_mock=use_mock)
    window.show()
    return app.exec()
