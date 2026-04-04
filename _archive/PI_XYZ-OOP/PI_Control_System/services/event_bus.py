"""
Thread-safe event bus for pub/sub communication.

Decouples services from GUI. Services publish events, GUI subscribes.
"""

from dataclasses import dataclass
from enum import Enum, auto
from typing import Callable, Any
from threading import Lock
import uuid


class EventType(Enum):
    """System events.

    Source: Derived from UI status messaging in legacy/PI_Control_GUI/main_gui.py
    """
    # Connection events
    CONNECTION_STARTED = auto()
    CONNECTION_SUCCEEDED = auto()
    CONNECTION_FAILED = auto()

    # Initialization events
    INITIALIZATION_STARTED = auto()
    INITIALIZATION_PROGRESS = auto()  # Per-axis updates
    INITIALIZATION_SUCCEEDED = auto()
    INITIALIZATION_FAILED = auto()

    # Motion events
    MOTION_STARTED = auto()
    MOTION_PROGRESS = auto()
    MOTION_COMPLETED = auto()
    MOTION_FAILED = auto()

    # Position events
    POSITION_UPDATED = auto()

    # State events
    STATE_CHANGED = auto()
    ERROR_OCCURRED = auto()


@dataclass
class Event:
    """Event with payload."""
    event_type: EventType
    data: Any = None


class SubscriptionToken:
    """Token for managing subscriptions.

    Allows safe unsubscribe without needing to keep callback reference.
    """

    def __init__(self, token_id: str, event_type: EventType, callback: Callable[[Event], None]):
        self.id = token_id
        self.event_type = event_type
        self.callback = callback


class EventBus:
    """Thread-safe pub/sub event bus.

    Decouples services from GUI. Services publish events,
    GUI subscribes to them.

    Design notes:
    - Callbacks execute synchronously in publisher's thread
    - GUI callbacks should use QMetaObject.invokeMethod to marshal to main thread
    - Lock protects subscription dictionary modifications
    - Returns tokens for safe unsubscribe
    """

    def __init__(self):
        self._subscribers: dict[EventType, list[SubscriptionToken]] = {}
        self._lock = Lock()

    def subscribe(self, event_type: EventType, callback: Callable[[Event], None]) -> SubscriptionToken:
        """Register callback for event type.

        Args:
            event_type: Event to listen for
            callback: Function called with Event object

        Returns:
            SubscriptionToken for later unsubscribe

        Example:
            >>> bus = EventBus()
            >>> token = bus.subscribe(EventType.CONNECTION_SUCCEEDED, on_connected)
            >>> # Later...
            >>> bus.unsubscribe(token)
        """
        token = SubscriptionToken(
            token_id=str(uuid.uuid4()),
            event_type=event_type,
            callback=callback
        )

        with self._lock:
            if event_type not in self._subscribers:
                self._subscribers[event_type] = []
            self._subscribers[event_type].append(token)

        return token

    def unsubscribe(self, token: SubscriptionToken) -> None:
        """Remove callback registration.

        Args:
            token: Token returned from subscribe()
        """
        with self._lock:
            if token.event_type in self._subscribers:
                self._subscribers[token.event_type] = [
                    t for t in self._subscribers[token.event_type]
                    if t.id != token.id
                ]

    def publish(self, event: Event) -> None:
        """Notify all subscribers of event.

        Callbacks execute synchronously in publisher's thread.
        GUI callbacks should marshal to main thread via QMetaObject.invokeMethod.

        Args:
            event: Event to publish

        Note:
            If a callback raises an exception, it is caught and logged
            to prevent breaking other subscribers.
        """
        with self._lock:
            # Get copy of token list to avoid issues if callbacks modify subscriptions
            tokens = self._subscribers.get(event.event_type, []).copy()

        for token in tokens:
            try:
                token.callback(event)
            except Exception as e:
                # Log error but don't break other subscribers
                print(f"Error in event callback for {event.event_type}: {e}")

    def clear_all(self) -> None:
        """Remove all subscriptions.

        Useful for cleanup or testing.
        """
        with self._lock:
            self._subscribers.clear()
