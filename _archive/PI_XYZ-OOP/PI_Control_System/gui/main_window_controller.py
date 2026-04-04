"""
Main window controller bridging services and widgets.

Responsibilities:
- Wire widget signals to service calls
- Subscribe to EventBus and marshal updates to widgets via Qt main thread
- Implement Spike 2.A pattern: QMetaObject.invokeMethod for thread-safe updates

Source: INTERFACES.md MainWindowController specification
"""

from collections import deque
from PySide6.QtCore import QObject, QMetaObject, Qt, QThread, QTimer, Slot
from PySide6.QtWidgets import QMessageBox

from ..services.event_bus import EventBus, EventType, Event
from ..services.connection_service import ConnectionService
from ..services.motion_service import MotionService
from ..core.models import Axis, Position, ConnectionState

# Import widgets
from .widgets.connection_panel import ConnectionPanel
from .widgets.position_display import PositionDisplayWidget
from .widgets.velocity_panel import VelocityPanel
from .widgets.manual_jog import ManualJogWidget
from .widgets.system_log import SystemLogWidget


class MainWindowController(QObject):
    """Controller bridging services and GUI widgets.

    Pattern: All EventBus callbacks execute in service threads.
    Use QMetaObject.invokeMethod to marshal updates to main Qt thread.

    Source: Spike 2.A threading pattern (APPENDICES.md)
    """

    def __init__(self,
                 event_bus: EventBus,
                 connection_service: ConnectionService,
                 motion_service: MotionService,
                 park_position: float = 200.0):
        """Initialize controller.

        Args:
            event_bus: EventBus for service events
            connection_service: Connection service
            motion_service: Motion service
            park_position: Park position for all axes (default 200.0)
        """
        super().__init__()

        self.event_bus = event_bus
        self.connection_service = connection_service
        self.motion_service = motion_service
        self.park_position = park_position

        # Widgets (set by main window)
        self.connection_panel: ConnectionPanel = None
        self.position_display: PositionDisplayWidget = None
        self.velocity_panel: VelocityPanel = None
        self.manual_jog: ManualJogWidget = None
        self.system_log: SystemLogWidget = None

        # Pending updates (for thread-safe marshalling)
        self._pending_state: ConnectionState = None
        self._pending_position: Position = None
        self._pending_logs: deque = deque()  # Buffer for all log messages
        self._pending_motion_enable: bool = None

        # Position polling timer
        self._position_timer = QTimer(self)
        self._position_timer.timeout.connect(self._poll_position)
        self._position_timer.setInterval(100)  # Poll every 100ms

        # Subscribe to all relevant events
        self._setup_event_subscriptions()

    def set_widgets(self,
                   connection_panel: ConnectionPanel,
                   position_display: PositionDisplayWidget,
                   velocity_panel: VelocityPanel,
                   manual_jog: ManualJogWidget,
                   sequence_panel,
                   system_log: SystemLogWidget):
        """Wire widgets to controller.

        Args:
            connection_panel: Connection controls widget
            position_display: Position display widget
            velocity_panel: Velocity control widget
            manual_jog: Manual jog widget
            sequence_panel: Automated sequence widget
            system_log: System log widget
        """
        self.connection_panel = connection_panel
        self.position_display = position_display
        self.velocity_panel = velocity_panel
        self.manual_jog = manual_jog
        self.sequence_panel = sequence_panel
        self.system_log = system_log

        # Connect widget signals to service calls
        self._connect_widget_signals()

    def _connect_widget_signals(self):
        """Wire widget signals to service methods."""
        # Connection panel
        self.connection_panel.connect_requested.connect(self._on_connect_requested)
        self.connection_panel.initialize_requested.connect(self._on_initialize_requested)
        self.connection_panel.disconnect_requested.connect(self._on_disconnect_requested)

        # Velocity panel
        self.velocity_panel.velocity_changed.connect(self._on_velocity_changed)

        # Manual jog
        self.manual_jog.jog_requested.connect(self._on_jog_requested)

        # Sequence panel
        self.sequence_panel.start_requested.connect(self._on_sequence_start_requested)
        self.sequence_panel.stop_requested.connect(self._on_sequence_stop_requested)

    def _setup_event_subscriptions(self):
        """Subscribe to EventBus events."""
        self.event_bus.subscribe(EventType.CONNECTION_STARTED, self._on_connection_started)
        self.event_bus.subscribe(EventType.CONNECTION_SUCCEEDED, self._on_connection_succeeded)
        self.event_bus.subscribe(EventType.CONNECTION_FAILED, self._on_connection_failed)

        self.event_bus.subscribe(EventType.INITIALIZATION_STARTED, self._on_initialization_started)
        self.event_bus.subscribe(EventType.INITIALIZATION_PROGRESS, self._on_initialization_progress)
        self.event_bus.subscribe(EventType.INITIALIZATION_SUCCEEDED, self._on_initialization_succeeded)
        self.event_bus.subscribe(EventType.INITIALIZATION_FAILED, self._on_initialization_failed)

        self.event_bus.subscribe(EventType.POSITION_UPDATED, self._on_position_updated)
        self.event_bus.subscribe(EventType.STATE_CHANGED, self._on_state_changed)
        self.event_bus.subscribe(EventType.ERROR_OCCURRED, self._on_error_occurred)

        self.event_bus.subscribe(EventType.MOTION_STARTED, self._on_motion_started)
        self.event_bus.subscribe(EventType.MOTION_COMPLETED, self._on_motion_completed)
        self.event_bus.subscribe(EventType.MOTION_FAILED, self._on_motion_failed)

    # Thread-safe invocation helper

    def _invoke_in_main_thread(self, method_name: str):
        """Invoke method in main thread, or directly if already in main thread.

        Args:
            method_name: Name of method to invoke
        """
        if QThread.currentThread() == self.thread():
            # Already in main thread, call directly
            getattr(self, method_name)()
        else:
            # Cross-thread, use queued invocation
            QMetaObject.invokeMethod(self, method_name, Qt.QueuedConnection)

    # Widget signal handlers (run in main thread)

    def _on_connect_requested(self):
        """Handle connect button click."""
        self.connection_service.connect()

    def _on_initialize_requested(self):
        """Handle initialize button click."""
        self.connection_service.initialize()

    def _on_disconnect_requested(self):
        """Handle disconnect button click - park then disconnect."""
        from PySide6.QtWidgets import QMessageBox
        from ..core.models import ConnectionState

        # Check if system is ready (initialized)
        if self.connection_service.state.connection == ConnectionState.READY:
            reply = QMessageBox.question(
                None,
                'Confirm Disconnect',
                'Park all axes before disconnecting?',
                QMessageBox.Yes | QMessageBox.No,
                QMessageBox.Yes
            )

            if reply == QMessageBox.Yes:
                try:
                    park_future = self.motion_service.park_all(self.park_position)
                    if park_future:
                        park_future.result(timeout=30)
                except Exception as e:
                    QMessageBox.warning(None, 'Park Error', f'Parking failed: {str(e)}')

        self.connection_service.disconnect()

    def _on_velocity_changed(self, axis: Axis, velocity: float):
        """Handle velocity change - apply to hardware."""
        try:
            # Get controller for this axis and set velocity
            manager = self.connection_service.manager
            if manager:
                controller = manager.get_controller(axis)
                controller.set_velocity(velocity)
                self._pending_logs.append((f"Velocity {axis.value}: {velocity:.1f} mm/s", "info"))
                self._invoke_in_main_thread("_apply_log_update")
        except Exception as e:
            self._pending_logs.append((f"Failed to set velocity: {str(e)}", "error"))
            self._invoke_in_main_thread("_apply_log_update")

    def _on_jog_requested(self, axis: Axis, distance: float):
        """Handle jog button click."""
        future = self.motion_service.move_axis_relative(axis, distance)
        # Future will complete async; updates come via events

    def _on_sequence_start_requested(self, waypoints: list):
        """Handle sequence start request."""
        from PySide6.QtWidgets import QMessageBox
        from ..core.models import SequenceConfig

        if not waypoints:
            QMessageBox.warning(None, 'No Waypoints', 'Please add waypoints before starting.')
            return

        reply = QMessageBox.question(
            None,
            'Confirm Sequence',
            f'Start automated sequence with {len(waypoints)} waypoints?',
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No
        )

        if reply != QMessageBox.Yes:
            return

        # Create sequence config and start
        config = SequenceConfig(waypoints=tuple(waypoints), park_when_complete=False)
        self.sequence_panel.set_running(True)
        self.sequence_panel.set_status(f"Running: 0/{len(waypoints)} waypoints", "info")

        try:
            future = self.motion_service.execute_sequence(config)
            # Add callback to reset UI when sequence completes
            future.add_done_callback(lambda f: self._on_sequence_completed(f))
        except Exception as e:
            self.sequence_panel.set_running(False)
            self.sequence_panel.set_status(f"Error: {str(e)}", "error")
            QMessageBox.warning(None, 'Sequence Error', f'Failed to start sequence: {str(e)}')

    def _on_sequence_stop_requested(self):
        """Handle sequence stop request."""
        self.motion_service.cancel_sequence()
        self.sequence_panel.set_running(False)
        self.sequence_panel.set_status("Stopped by user", "info")

    def _on_sequence_completed(self, future):
        """Handle sequence completion (runs in worker thread)."""
        try:
            future.result()  # Check for exceptions
            # Success - reset UI
            self._invoke_in_main_thread("_reset_sequence_ui_success")
        except Exception as e:
            # Failure - reset UI with error
            self._pending_logs.append((f"Sequence failed: {str(e)}", "error"))
            self._invoke_in_main_thread("_reset_sequence_ui_error")
            self._invoke_in_main_thread("_apply_log_update")

    # EventBus callbacks (run in service threads - marshal to main thread)

    def _on_connection_started(self, event: Event):
        """Handle CONNECTION_STARTED event."""
        self._pending_state = ConnectionState.CONNECTING
        self._pending_logs.append(("Connecting to hardware...", "info"))
        self._invoke_in_main_thread("_apply_state_update")
        self._invoke_in_main_thread("_apply_log_update")

    def _on_connection_succeeded(self, event: Event):
        """Handle CONNECTION_SUCCEEDED event."""
        self._pending_state = ConnectionState.CONNECTED
        self._pending_logs.append(("Connected successfully", "success"))
        self._invoke_in_main_thread("_apply_state_update")
        self._invoke_in_main_thread("_apply_log_update")

    def _on_connection_failed(self, event: Event):
        """Handle CONNECTION_FAILED event."""
        error_detail = event.data
        self._pending_state = ConnectionState.ERROR
        self._pending_logs.append((f"Connection failed: {error_detail.get('message', 'Unknown error')}", "error"))
        self._invoke_in_main_thread("_apply_state_update")
        self._invoke_in_main_thread("_apply_log_update")

    def _on_initialization_started(self, event: Event):
        """Handle INITIALIZATION_STARTED event."""
        self._pending_state = ConnectionState.INITIALIZING
        self._pending_logs.append(("Initializing axes...", "info"))
        self._invoke_in_main_thread("_apply_state_update")
        self._invoke_in_main_thread("_apply_log_update")

    def _on_initialization_progress(self, event: Event):
        """Handle INITIALIZATION_PROGRESS event."""
        axis = event.data.get('axis')
        self._pending_logs.append((f"Referencing {axis}...", "info"))
        self._invoke_in_main_thread("_apply_log_update")

    def _on_initialization_succeeded(self, event: Event):
        """Handle INITIALIZATION_SUCCEEDED event."""
        self._pending_state = ConnectionState.READY
        self._pending_logs.append(("Initialization complete - system ready", "success"))
        self._pending_motion_enable = True
        self._invoke_in_main_thread("_apply_state_update")
        self._invoke_in_main_thread("_apply_log_update")
        self._invoke_in_main_thread("_apply_motion_enable_update")
        self._invoke_in_main_thread("_start_position_polling")

    def _on_initialization_failed(self, event: Event):
        """Handle INITIALIZATION_FAILED event."""
        error_detail = event.data
        self._pending_state = ConnectionState.ERROR
        self._pending_logs.append((f"Initialization failed: {error_detail.get('message', 'Unknown error')}", "error"))
        self._invoke_in_main_thread("_apply_state_update")
        self._invoke_in_main_thread("_apply_log_update")

    def _on_position_updated(self, event: Event):
        """Handle POSITION_UPDATED event."""
        self._pending_position = event.data
        self._invoke_in_main_thread("_apply_position_update")

    def _on_state_changed(self, event: Event):
        """Handle STATE_CHANGED event."""
        data = event.data

        # Event payload may be SystemState or dict depending on publisher
        if hasattr(data, "connection"):
            state = data.connection
        elif isinstance(data, dict):
            state = data.get("connection")
        else:
            state = None

        if state:
            self._pending_state = state
            self._invoke_in_main_thread("_apply_state_update")

    def _on_error_occurred(self, event: Event):
        """Handle ERROR_OCCURRED event."""
        message = self._extract_message(event.data, default="Unknown error")
        self._pending_logs.append((f"Error: {message}", "error"))
        self._invoke_in_main_thread("_apply_log_update")

    def _on_motion_started(self, event: Event):
        """Handle MOTION_STARTED event."""
        description = self._extract_motion_description(event.data)
        self._pending_logs.append((f"Moving {description}...", "info"))
        self._invoke_in_main_thread("_apply_log_update")

    def _on_motion_completed(self, event: Event):
        """Handle MOTION_COMPLETED event."""
        self._pending_logs.append(("Motion completed", "success"))
        self._invoke_in_main_thread("_apply_log_update")

    def _on_motion_failed(self, event: Event):
        """Handle MOTION_FAILED event."""
        message = self._extract_message(event.data, default="Unknown error")
        self._pending_logs.append((f"Motion failed: {message}", "error"))
        self._invoke_in_main_thread("_apply_log_update")

    # Main-thread update methods (called via invokeMethod)

    @Slot()
    def _apply_state_update(self):
        """Apply pending state update (main thread)."""
        if self._pending_state is None:
            return

        state = self._pending_state
        self._pending_state = None

        if self.connection_panel:
            self.connection_panel.update_state(state)

        # Clear position display on disconnect
        if state == ConnectionState.DISCONNECTED and self.position_display:
            self.position_display.clear_position()

        # Stop position polling if not ready
        if state == ConnectionState.READY:
            self._start_position_polling()
        else:
            self._stop_position_polling()

        # Disable motion controls if not ready
        if state != ConnectionState.READY:
            self._enable_motion_controls(False)

    @Slot()
    def _apply_position_update(self):
        """Apply pending position update (main thread)."""
        if self._pending_position is None:
            return

        position = self._pending_position
        self._pending_position = None

        if self.position_display:
            self.position_display.update_position(position)

    @Slot()
    def _apply_log_update(self):
        """Apply all pending log messages (main thread)."""
        if not self.system_log:
            return

        # Drain the entire deque to preserve all log entries
        while self._pending_logs:
            message, level = self._pending_logs.popleft()
            self.system_log.append_message(message, level)

    @Slot()
    def _apply_motion_enable_update(self):
        """Apply pending motion enable state (main thread)."""
        if self._pending_motion_enable is None:
            return

        enabled = self._pending_motion_enable
        self._pending_motion_enable = None

        self._enable_motion_controls(enabled)

    def _enable_motion_controls(self, enabled: bool):
        """Enable/disable motion controls (main thread)."""
        if self.velocity_panel:
            self.velocity_panel.set_enabled(enabled)
        if self.manual_jog:
            self.manual_jog.set_enabled(enabled)

    @Slot()
    def _poll_position(self):
        """Poll hardware for current position (main thread)."""
        try:
            manager = self.connection_service.manager
            if manager:
                position = manager.get_position_snapshot()
                if self.position_display:
                    self.position_display.update_position(position)
        except Exception:
            # Silently ignore polling errors (e.g., hardware disconnected)
            pass

    @Slot()
    def _start_position_polling(self):
        """Start position polling timer (main thread)."""
        if not self._position_timer.isActive():
            self._position_timer.start()

    @Slot()
    def _stop_position_polling(self):
        """Stop position polling timer (main thread)."""
        if self._position_timer.isActive():
            self._position_timer.stop()

    @Slot()
    def _reset_sequence_ui_success(self):
        """Reset sequence UI after successful completion (main thread)."""
        if self.sequence_panel:
            self.sequence_panel.set_running(False)
            self.sequence_panel.set_status("Sequence completed successfully", "success")

    @Slot()
    def _reset_sequence_ui_error(self):
        """Reset sequence UI after error (main thread)."""
        if self.sequence_panel:
            self.sequence_panel.set_running(False)
            self.sequence_panel.set_status("Sequence failed - see log", "error")

    def _extract_message(self, data, default: str) -> str:
        """Extract message string from event payload."""
        if isinstance(data, dict):
            return str(data.get("message", default))
        if data is None:
            return default
        return str(data)

    def _extract_motion_description(self, data) -> str:
        """Derive human-readable motion description from payload."""
        if isinstance(data, dict):
            return str(data.get("axis", "axes"))
        if data:
            return str(data)
        return "axes"
