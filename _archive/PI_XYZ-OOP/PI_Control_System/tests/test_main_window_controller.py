"""
Tests for MainWindowController (service-widget bridge).

Verifies signal mapping and thread-safe event marshalling.
"""

import os
import pytest
import time
from unittest.mock import Mock, MagicMock
from PySide6.QtWidgets import QApplication
from PySide6.QtCore import QTimer, QCoreApplication

from PI_Control_System.core.models import Axis, Position, ConnectionState, SystemState
from PI_Control_System.services.event_bus import EventBus, EventType, Event
from PI_Control_System.gui.main_window_controller import MainWindowController
from PI_Control_System.gui.widgets.connection_panel import ConnectionPanel
from PI_Control_System.gui.widgets.position_display import PositionDisplayWidget
from PI_Control_System.gui.widgets.velocity_panel import VelocityPanel
from PI_Control_System.gui.widgets.manual_jog import ManualJogWidget
from PI_Control_System.gui.widgets.system_log import SystemLogWidget


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
def event_bus():
    """EventBus fixture."""
    return EventBus()


@pytest.fixture
def mock_services():
    """Mock service fixtures."""
    connection_service = Mock()
    motion_service = Mock()
    return connection_service, motion_service


@pytest.fixture
def controller(qapp, event_bus, mock_services):
    """Controller with mocked services."""
    connection_service, motion_service = mock_services
    ctrl = MainWindowController(event_bus, connection_service, motion_service)
    return ctrl


@pytest.fixture
def widgets(qapp):
    """Create widget instances."""
    from PI_Control_System.gui.widgets.sequence_panel import SequencePanel
    return {
        'connection': ConnectionPanel(),
        'position': PositionDisplayWidget(),
        'velocity': VelocityPanel(),
        'jog': ManualJogWidget(),
        'sequence': SequencePanel(),
        'log': SystemLogWidget()
    }


def test_controller_creation(controller):
    """Should create controller without errors."""
    assert controller is not None
    assert hasattr(controller, 'event_bus')
    assert hasattr(controller, 'connection_service')
    assert hasattr(controller, 'motion_service')


def test_set_widgets(controller, widgets):
    """Should wire widgets to controller."""
    controller.set_widgets(
        widgets['connection'],
        widgets['position'],
        widgets['velocity'],
        widgets['jog'],
        widgets['sequence'],
        widgets['log']
    )

    assert controller.connection_panel == widgets['connection']
    assert controller.position_display == widgets['position']
    assert controller.velocity_panel == widgets['velocity']
    assert controller.manual_jog == widgets['jog']
    assert controller.system_log == widgets['log']


def test_connect_button_calls_service(controller, widgets, mock_services):
    """Should call connection_service.connect when connect button clicked."""
    connection_service, _ = mock_services

    controller.set_widgets(
        widgets['connection'],
        widgets['position'],
        widgets['velocity'],
        widgets['jog'],
        widgets['sequence'],
        widgets['log']
    )

    # Simulate button click
    widgets['connection'].connect_requested.emit()

    connection_service.connect.assert_called_once()


def test_initialize_button_calls_service(controller, widgets, mock_services):
    """Should call connection_service.initialize when initialize button clicked."""
    connection_service, _ = mock_services

    controller.set_widgets(
        widgets['connection'],
        widgets['position'],
        widgets['velocity'],
        widgets['jog'],
        widgets['sequence'],
        widgets['log']
    )

    # Simulate button click
    widgets['connection'].initialize_requested.emit()

    connection_service.initialize.assert_called_once()


def test_disconnect_button_calls_service(controller, widgets, mock_services):
    """Should call connection_service.disconnect when disconnect button clicked."""
    connection_service, _ = mock_services

    controller.set_widgets(
        widgets['connection'],
        widgets['position'],
        widgets['velocity'],
        widgets['jog'],
        widgets['sequence'],
        widgets['log']
    )

    # Simulate button click
    widgets['connection'].disconnect_requested.emit()

    connection_service.disconnect.assert_called_once()


def test_jog_button_calls_motion_service(controller, widgets, mock_services):
    """Should call motion_service.move_axis_relative when jog button clicked."""
    _, motion_service = mock_services
    motion_service.move_axis_relative.return_value = Mock()  # Mock future

    controller.set_widgets(
        widgets['connection'],
        widgets['position'],
        widgets['velocity'],
        widgets['jog'],
        widgets['sequence'],
        widgets['log']
    )

    # Simulate jog request
    widgets['jog'].jog_requested.emit(Axis.X, 5.0)

    motion_service.move_axis_relative.assert_called_once_with(Axis.X, 5.0)


def test_connection_started_event_updates_ui(qapp, controller, widgets, event_bus):
    """Should update UI when CONNECTION_STARTED event published."""
    controller.set_widgets(
        widgets['connection'],
        widgets['position'],
        widgets['velocity'],
        widgets['jog'],
        widgets['sequence'],
        widgets['log']
    )

    # Publish event
    event = Event(EventType.CONNECTION_STARTED, {})
    event_bus.publish(event)

    # Process Qt event loop to handle queued invocations
    # Multiple processEvents calls ensure queued invocations are processed
    for _ in range(5):
        qapp.processEvents()

    # Check state updated
    assert widgets['connection']._current_state == ConnectionState.CONNECTING


def test_connection_succeeded_event_updates_ui(qapp, controller, widgets, event_bus):
    """Should update UI when CONNECTION_SUCCEEDED event published."""
    controller.set_widgets(
        widgets['connection'],
        widgets['position'],
        widgets['velocity'],
        widgets['jog'],
        widgets['sequence'],
        widgets['log']
    )

    # Publish event
    event = Event(EventType.CONNECTION_SUCCEEDED, {})
    event_bus.publish(event)

    # Process Qt event loop
    for _ in range(5):
        qapp.processEvents()

    # Check state updated
    assert widgets['connection']._current_state == ConnectionState.CONNECTED


def test_position_updated_event_updates_display(qapp, controller, widgets, event_bus):
    """Should update position display when POSITION_UPDATED event published."""
    controller.set_widgets(
        widgets['connection'],
        widgets['position'],
        widgets['velocity'],
        widgets['jog'],
        widgets['sequence'],
        widgets['log']
    )

    # Publish position update
    position = Position(12.5, 34.6, 78.9)
    event = Event(EventType.POSITION_UPDATED, position)
    event_bus.publish(event)

    # Process Qt event loop
    for _ in range(5):
        qapp.processEvents()

    # Check position displayed
    assert widgets['position'].position_labels[Axis.X].text() == "12.500"
    assert widgets['position'].position_labels[Axis.Y].text() == "34.600"
    assert widgets['position'].position_labels[Axis.Z].text() == "78.900"


def test_initialization_succeeded_enables_motion_controls(qapp, controller, widgets, event_bus):
    """Should enable motion controls when initialization succeeds."""
    controller.set_widgets(
        widgets['connection'],
        widgets['position'],
        widgets['velocity'],
        widgets['jog'],
        widgets['sequence'],
        widgets['log']
    )

    # Initially disabled
    widgets['velocity'].set_enabled(False)
    widgets['jog'].set_enabled(False)

    # Publish success event
    event = Event(EventType.INITIALIZATION_SUCCEEDED, {})
    event_bus.publish(event)

    # Process Qt event loop
    for _ in range(5):
        qapp.processEvents()

    # Motion controls should be enabled
    assert widgets['velocity'].velocity_spinboxes[Axis.X].isEnabled()
    assert widgets['jog'].jog_buttons[Axis.X][0].isEnabled()


def test_disconnect_clears_position_display(qapp, controller, widgets, event_bus):
    """Should clear position display on disconnect."""
    controller.set_widgets(
        widgets['connection'],
        widgets['position'],
        widgets['velocity'],
        widgets['jog'],
        widgets['sequence'],
        widgets['log']
    )

    # Set position
    widgets['position'].update_position(Position(10.0, 20.0, 30.0))

    # Simulate disconnect (state change to DISCONNECTED)
    event = Event(EventType.STATE_CHANGED, {'connection': ConnectionState.DISCONNECTED})
    event_bus.publish(event)

    # Process Qt event loop
    for _ in range(5):
        qapp.processEvents()

    # Position should be cleared
    assert widgets['position'].position_labels[Axis.X].text() == "---"


def test_state_changed_handles_system_state_payload(qapp, controller, widgets, event_bus):
    """Should handle STATE_CHANGED events that pass SystemState objects."""
    controller.set_widgets(
        widgets['connection'],
        widgets['position'],
        widgets['velocity'],
        widgets['jog'],
        widgets['sequence'],
        widgets['log']
    )

    system_state = SystemState(
        connection=ConnectionState.CONNECTED,
        initialization=None,
        is_sequence_running=False
    )

    event_bus.publish(Event(EventType.STATE_CHANGED, system_state))

    for _ in range(5):
        qapp.processEvents()

    assert widgets['connection']._current_state == ConnectionState.CONNECTED


def test_rapid_events_preserve_all_log_messages(qapp, controller, widgets, event_bus):
    """Should preserve all log messages when events fire rapidly."""
    controller.set_widgets(
        widgets['connection'],
        widgets['position'],
        widgets['velocity'],
        widgets['jog'],
        widgets['sequence'],
        widgets['log']
    )

    # Publish multiple events in rapid succession (synchronous EventBus)
    event_bus.publish(Event(EventType.CONNECTION_STARTED, {}))
    event_bus.publish(Event(EventType.CONNECTION_FAILED, {'message': 'Timeout'}))
    event_bus.publish(Event(EventType.ERROR_OCCURRED, {'message': 'Hardware fault'}))

    # Process Qt event loop
    for _ in range(5):
        qapp.processEvents()

    # All three messages should appear in log
    log_text = widgets['log'].log_text.toPlainText()
    assert "Connecting to hardware" in log_text
    assert "Connection failed: Timeout" in log_text
    assert "Error: Hardware fault" in log_text


def test_motion_started_string_payload(qapp, controller, widgets, event_bus):
    """Should handle motion started events with string payload."""
    controller.set_widgets(
        widgets['connection'],
        widgets['position'],
        widgets['velocity'],
        widgets['jog'],
        widgets['sequence'],
        widgets['log']
    )

    event_bus.publish(Event(EventType.MOTION_STARTED, "Move axis X absolute"))

    for _ in range(5):
        qapp.processEvents()

    assert "Move axis X absolute" in widgets['log'].log_text.toPlainText()


def test_error_string_payload(qapp, controller, widgets, event_bus):
    """Should handle error events with string payload."""
    controller.set_widgets(
        widgets['connection'],
        widgets['position'],
        widgets['velocity'],
        widgets['jog'],
        widgets['sequence'],
        widgets['log']
    )

    event_bus.publish(Event(EventType.ERROR_OCCURRED, "Motion timeout"))

    for _ in range(5):
        qapp.processEvents()

    assert "Motion timeout" in widgets['log'].log_text.toPlainText()


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
