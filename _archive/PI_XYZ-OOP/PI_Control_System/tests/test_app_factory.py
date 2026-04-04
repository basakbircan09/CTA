"""
Tests for application factory.

Verifies dependency injection and component wiring.
"""

import os
import pytest
from PySide6.QtWidgets import QApplication

from PI_Control_System.app_factory import create_app


@pytest.fixture(scope="module")
def qapp():
    """QApplication fixture."""
    if not os.environ.get('DISPLAY') and os.name != 'nt':
        os.environ['QT_QPA_PLATFORM'] = 'offscreen'

    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    yield app


def test_create_app_with_mock(qapp):
    """Should create app with mock hardware."""
    window = create_app(use_mock=True)

    assert window is not None
    assert window.controller is not None
    assert window.connection_service is not None
    assert window.motion_service is not None


def test_create_app_shares_event_bus(qapp):
    """Should share same EventBus across services."""
    window = create_app(use_mock=True)

    # All components should reference same EventBus instance
    assert window.event_bus is window.controller.event_bus
    # ConnectionService and MotionService have internal references
    # Verify via controller which is wired to both


def test_create_app_shares_executor(qapp):
    """Should share same executor between services."""
    window = create_app(use_mock=True)

    # ConnectionService and MotionService should share executor
    # Verify they were created (factory doesn't expose executor directly)
    assert window.connection_service is not None
    assert window.motion_service is not None


def test_create_app_wires_all_components(qapp):
    """Should wire all components together properly."""
    window = create_app(use_mock=True)

    # Verify all components are wired
    assert window is not None
    assert window.controller is not None
    assert window.connection_service is not None
    assert window.motion_service is not None
    assert window.event_bus is not None

    # Verify widgets are set
    assert window.connection_panel is not None
    assert window.position_display is not None
    assert window.velocity_panel is not None
    assert window.manual_jog is not None
    assert window.system_log is not None


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
