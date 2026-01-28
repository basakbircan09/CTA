"""
Tests for MainWindow assembly.

Verifies window instantiation and widget composition.
"""

import os
import pytest
from unittest.mock import Mock
from PySide6.QtWidgets import QApplication

from PI_Control_System.core.models import Axis
from PI_Control_System.services.event_bus import EventBus
from PI_Control_System.gui.main_window import MainWindow


@pytest.fixture(scope="module")
def qapp():
    """QApplication fixture."""
    if not os.environ.get('DISPLAY') and os.name != 'nt':
        os.environ['QT_QPA_PLATFORM'] = 'offscreen'

    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    yield app


@pytest.fixture
def mock_services():
    """Mock service fixtures."""
    event_bus = EventBus()
    connection_service = Mock()
    motion_service = Mock()
    return event_bus, connection_service, motion_service


def test_main_window_instantiation(qapp, mock_services):
    """Should create MainWindow without errors."""
    event_bus, connection_service, motion_service = mock_services

    window = MainWindow(event_bus, connection_service, motion_service)

    assert window is not None
    assert window.windowTitle() == "PI Stage Control System"


def test_main_window_has_all_widgets(qapp, mock_services):
    """Should instantiate all required widgets."""
    event_bus, connection_service, motion_service = mock_services

    window = MainWindow(event_bus, connection_service, motion_service)

    # Verify widgets exist
    assert hasattr(window, 'connection_panel')
    assert hasattr(window, 'position_display')
    assert hasattr(window, 'velocity_panel')
    assert hasattr(window, 'manual_jog')
    assert hasattr(window, 'system_log')

    # Verify widgets are not None
    assert window.connection_panel is not None
    assert window.position_display is not None
    assert window.velocity_panel is not None
    assert window.manual_jog is not None
    assert window.system_log is not None


def test_main_window_has_controller(qapp, mock_services):
    """Should create controller and wire widgets."""
    event_bus, connection_service, motion_service = mock_services

    window = MainWindow(event_bus, connection_service, motion_service)

    # Verify controller exists
    assert hasattr(window, 'controller')
    assert window.controller is not None

    # Verify controller has widgets wired
    assert window.controller.connection_panel == window.connection_panel
    assert window.controller.position_display == window.position_display
    assert window.controller.velocity_panel == window.velocity_panel
    assert window.controller.manual_jog == window.manual_jog
    assert window.controller.system_log == window.system_log


def test_main_window_central_widget(qapp, mock_services):
    """Should have scroll area as central widget."""
    event_bus, connection_service, motion_service = mock_services

    window = MainWindow(event_bus, connection_service, motion_service)

    # Verify scroll area is central widget
    central = window.centralWidget()
    assert central is not None
    from PySide6.QtWidgets import QScrollArea
    assert isinstance(central, QScrollArea)
    # Verify scroll area has content widget
    assert central.widget() is not None


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
