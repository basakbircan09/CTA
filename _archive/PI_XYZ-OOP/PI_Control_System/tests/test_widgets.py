"""
Tests for GUI widgets (rendering with stubbed data).

These tests verify widgets can be instantiated and updated without
requiring service layer dependencies.
"""

import os
import pytest
from PySide6.QtWidgets import QApplication

from PI_Control_System.core.models import Axis, Position, ConnectionState
from PI_Control_System.gui.widgets.connection_panel import ConnectionPanel
from PI_Control_System.gui.widgets.position_display import PositionDisplayWidget
from PI_Control_System.gui.widgets.velocity_panel import VelocityPanel
from PI_Control_System.gui.widgets.manual_jog import ManualJogWidget
from PI_Control_System.gui.widgets.system_log import SystemLogWidget


@pytest.fixture(scope="module")
def qapp():
    """QApplication fixture for all widget tests.

    Forces offscreen platform for headless environments (CI, SSH sessions).
    """
    # Force offscreen platform if no DISPLAY available (headless environment)
    if not os.environ.get('DISPLAY') and os.name != 'nt':
        os.environ['QT_QPA_PLATFORM'] = 'offscreen'

    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    yield app


def test_connection_panel_renders(qapp):
    """Should create ConnectionPanel without errors."""
    panel = ConnectionPanel()
    assert panel is not None
    assert hasattr(panel, 'connect_requested')
    assert hasattr(panel, 'initialize_requested')
    assert hasattr(panel, 'disconnect_requested')


def test_connection_panel_state_updates(qapp):
    """Should update UI when state changes."""
    panel = ConnectionPanel()

    # Test different states
    panel.update_state(ConnectionState.DISCONNECTED)
    assert panel.status_label.text() == "Disconnected"
    assert panel.connect_btn.isEnabled()
    assert not panel.initialize_btn.isEnabled()
    assert not panel.disconnect_btn.isEnabled()

    panel.update_state(ConnectionState.CONNECTED)
    assert panel.status_label.text() == "Connected"
    assert not panel.connect_btn.isEnabled()
    assert panel.initialize_btn.isEnabled()
    assert panel.disconnect_btn.isEnabled()

    panel.update_state(ConnectionState.READY)
    assert panel.status_label.text() == "Ready"
    assert not panel.initialize_btn.isEnabled()


def test_position_display_renders(qapp):
    """Should create PositionDisplayWidget without errors."""
    widget = PositionDisplayWidget()
    assert widget is not None
    assert Axis.X in widget.position_labels
    assert Axis.Y in widget.position_labels
    assert Axis.Z in widget.position_labels


def test_position_display_updates(qapp):
    """Should update position labels when position changes."""
    widget = PositionDisplayWidget()

    # Initial state
    assert widget.position_labels[Axis.X].text() == "---"

    # Update position
    pos = Position(12.345, 67.890, 23.456)
    widget.update_position(pos)

    assert widget.position_labels[Axis.X].text() == "12.345"
    assert widget.position_labels[Axis.Y].text() == "67.890"
    assert widget.position_labels[Axis.Z].text() == "23.456"

    # Clear
    widget.clear_position()
    assert widget.position_labels[Axis.X].text() == "---"


def test_velocity_panel_renders(qapp):
    """Should create VelocityPanel without errors."""
    panel = VelocityPanel(max_velocity=20.0, default_velocity=10.0)
    assert panel is not None
    assert hasattr(panel, 'velocity_changed')
    assert Axis.X in panel.velocity_spinboxes
    assert Axis.Y in panel.velocity_spinboxes
    assert Axis.Z in panel.velocity_spinboxes


def test_velocity_panel_get_set(qapp):
    """Should get/set velocity values."""
    panel = VelocityPanel(max_velocity=20.0, default_velocity=10.0)

    # Check defaults
    assert panel.get_velocity(Axis.X) == 10.0

    # Set new value
    panel.set_velocity(Axis.X, 15.0)
    assert panel.get_velocity(Axis.X) == 15.0

    # Enable/disable
    panel.set_enabled(False)
    assert not panel.velocity_spinboxes[Axis.X].isEnabled()

    panel.set_enabled(True)
    assert panel.velocity_spinboxes[Axis.X].isEnabled()


def test_velocity_panel_slider_sync(qapp):
    """Should update spinbox value during programmatic updates."""
    panel = VelocityPanel(max_velocity=20.0, default_velocity=10.0)

    # Set velocity programmatically
    panel.set_velocity(Axis.X, 18.0)

    # Spinbox should reflect new value
    assert panel.velocity_spinboxes[Axis.X].value() == 18.0

    # Set to different value
    panel.set_velocity(Axis.X, 5.0)
    assert panel.velocity_spinboxes[Axis.X].value() == 5.0


def test_manual_jog_renders(qapp):
    """Should create ManualJogWidget without errors."""
    widget = ManualJogWidget(default_step=1.0)
    assert widget is not None
    assert hasattr(widget, 'jog_requested')
    assert Axis.X in widget.jog_buttons
    assert Axis.Y in widget.jog_buttons
    assert Axis.Z in widget.jog_buttons


def test_manual_jog_enable_disable(qapp):
    """Should enable/disable jog buttons."""
    widget = ManualJogWidget()

    # Initially enabled (if created standalone)
    widget.set_enabled(False)
    neg_btn, pos_btn = widget.jog_buttons[Axis.X]
    assert not neg_btn.isEnabled()
    assert not pos_btn.isEnabled()

    widget.set_enabled(True)
    assert neg_btn.isEnabled()
    assert pos_btn.isEnabled()


def test_system_log_renders(qapp):
    """Should create SystemLogWidget without errors."""
    widget = SystemLogWidget()
    assert widget is not None


def test_system_log_messages(qapp):
    """Should append and clear messages."""
    widget = SystemLogWidget()

    # Initially empty
    assert widget.log_text.toPlainText() == ""

    # Append messages
    widget.append_message("Test info message", "info")
    widget.append_message("Test error message", "error")

    text = widget.log_text.toPlainText()
    assert "Test info message" in text
    assert "Test error message" in text

    # Clear
    widget.clear()
    assert widget.log_text.toPlainText() == ""


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
