"""
Connection service for managing hardware lifecycle.

Orchestrates connection and initialization for all axes.
Source: legacy/PI_Control_GUI/hardware_controller.py (connection/init operations)
"""

from concurrent.futures import ThreadPoolExecutor, Future
from typing import Optional

from ..core.hardware.interfaces import AxisControllerManager
from ..core.models import ConnectionState, SystemState, InitializationState
from ..core.errors import ConnectionError, InitializationError
from .event_bus import EventBus, Event, EventType


class ConnectionService:
    """Connection lifecycle management service.

    Responsibilities:
    - Coordinate connect/initialize/disconnect operations
    - Publish state transition events
    - Run blocking operations in background threads
    - Track system state

    Source: legacy/PI_Control_GUI/hardware_controller.py:35-120, 330-346
    """

    def __init__(self, manager: AxisControllerManager, event_bus: EventBus,
                 executor: Optional[ThreadPoolExecutor] = None):
        """Initialize connection service.

        Args:
            manager: Hardware controller manager
            event_bus: Event bus for publishing state changes
            executor: Thread pool for async operations (creates default if None)
        """
        self._manager = manager
        self._event_bus = event_bus
        self._executor = executor or ThreadPoolExecutor(max_workers=4)
        self._owns_executor = executor is None

        self._connection_state = ConnectionState.DISCONNECTED
        self._init_state = InitializationState.NOT_INITIALIZED

    @property
    def manager(self) -> AxisControllerManager:
        """Get hardware controller manager."""
        return self._manager

    @property
    def state(self) -> SystemState:
        """Get current system state snapshot."""
        return SystemState(
            connection=self._connection_state,
            initialization=self._init_state,
            is_sequence_running=False  # Managed by MotionService
        )

    def connect(self) -> Future[None]:
        """Connect to all axis controllers asynchronously.

        Publishes:
            - CONNECTION_STARTED (immediate)
            - CONNECTION_SUCCEEDED or CONNECTION_FAILED (after completion)
            - STATE_CHANGED (on state transitions)

        Returns:
            Future that completes when connection finishes

        Source: legacy/PI_Control_GUI/hardware_controller.py:35-57
        """
        self._connection_state = ConnectionState.CONNECTING
        self._event_bus.publish(Event(EventType.CONNECTION_STARTED))
        self._publish_state_change()

        def _connect():
            try:
                self._manager.connect_all()

                self._connection_state = ConnectionState.CONNECTED
                self._event_bus.publish(Event(EventType.CONNECTION_SUCCEEDED))
                self._publish_state_change()

            except Exception as e:
                self._connection_state = ConnectionState.ERROR
                self._event_bus.publish(Event(EventType.CONNECTION_FAILED, data=str(e)))
                self._publish_state_change()
                self._event_bus.publish(Event(EventType.ERROR_OCCURRED, data=str(e)))
                raise ConnectionError(f"Connection failed: {e}") from e

        return self._executor.submit(_connect)

    def initialize(self) -> Future[None]:
        """Initialize and reference all axes asynchronously.

        Must be called after successful connect().

        Publishes:
            - INITIALIZATION_STARTED (immediate)
            - INITIALIZATION_PROGRESS (per-axis updates)
            - INITIALIZATION_SUCCEEDED or INITIALIZATION_FAILED (after completion)
            - STATE_CHANGED (on state transitions)

        Returns:
            Future that completes when initialization finishes

        Source: legacy/PI_Control_GUI/hardware_controller.py:59-120
        """
        if self._connection_state != ConnectionState.CONNECTED:
            error = InitializationError("Cannot initialize: not connected")
            self._event_bus.publish(Event(EventType.INITIALIZATION_FAILED, data=str(error)))
            raise error

        self._connection_state = ConnectionState.INITIALIZING
        self._init_state = InitializationState.INITIALIZING
        self._event_bus.publish(Event(EventType.INITIALIZATION_STARTED))
        self._publish_state_change()

        def _initialize():
            try:
                # Note: manager publishes INITIALIZATION_PROGRESS events internally
                # if we want granular per-axis updates
                self._manager.initialize_all()

                self._connection_state = ConnectionState.READY
                self._init_state = InitializationState.INITIALIZED
                self._event_bus.publish(Event(EventType.INITIALIZATION_SUCCEEDED))
                self._publish_state_change()

            except Exception as e:
                self._connection_state = ConnectionState.ERROR
                self._init_state = InitializationState.FAILED
                self._event_bus.publish(Event(EventType.INITIALIZATION_FAILED, data=str(e)))
                self._publish_state_change()
                self._event_bus.publish(Event(EventType.ERROR_OCCURRED, data=str(e)))
                raise InitializationError(f"Initialization failed: {e}") from e

        return self._executor.submit(_initialize)

    def disconnect(self) -> None:
        """Disconnect all controllers synchronously.

        Best-effort cleanup, does not raise exceptions.

        Publishes:
            - STATE_CHANGED (to DISCONNECTED)

        Source: legacy/PI_Control_GUI/hardware_controller.py:330-346
        """
        try:
            self._manager.disconnect_all()
        except Exception as e:
            print(f"Error during disconnect: {e}")
        finally:
            self._connection_state = ConnectionState.DISCONNECTED
            self._init_state = InitializationState.NOT_INITIALIZED
            self._publish_state_change()

    def is_ready(self) -> bool:
        """Check if system is ready for motion commands."""
        return self._connection_state == ConnectionState.READY

    def shutdown(self) -> None:
        """Shutdown service and cleanup resources."""
        self.disconnect()

        if self._owns_executor:
            self._executor.shutdown(wait=True)

    def _publish_state_change(self) -> None:
        """Publish state change payload (dict for compatibility)."""
        payload = {
            "connection": self._connection_state,
            "initialization": self._init_state,
            "system_state": self.state,
        }
        self._event_bus.publish(Event(EventType.STATE_CHANGED, data=payload))
