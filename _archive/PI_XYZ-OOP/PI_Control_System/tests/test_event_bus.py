"""
Tests for EventBus.

Verifies:
- Subscribe/unsubscribe/publish mechanics
- Thread safety
- Error handling in callbacks
- Token-based subscription management
"""

import pytest
from threading import Thread
from PI_Control_System.services.event_bus import EventBus, Event, EventType


def test_event_bus_subscribe_and_publish():
    """Basic subscribe and publish."""
    bus = EventBus()
    received = []

    def callback(event: Event):
        received.append(event)

    token = bus.subscribe(EventType.CONNECTION_SUCCEEDED, callback)
    bus.publish(Event(EventType.CONNECTION_SUCCEEDED, data="test"))

    assert len(received) == 1
    assert received[0].event_type == EventType.CONNECTION_SUCCEEDED
    assert received[0].data == "test"


def test_event_bus_multiple_subscribers():
    """Multiple subscribers to same event."""
    bus = EventBus()
    received1 = []
    received2 = []

    bus.subscribe(EventType.MOTION_COMPLETED, lambda e: received1.append(e))
    bus.subscribe(EventType.MOTION_COMPLETED, lambda e: received2.append(e))

    bus.publish(Event(EventType.MOTION_COMPLETED, data="done"))

    assert len(received1) == 1
    assert len(received2) == 1


def test_event_bus_unsubscribe():
    """Unsubscribe removes callback."""
    bus = EventBus()
    received = []

    token = bus.subscribe(EventType.POSITION_UPDATED, lambda e: received.append(e))

    # Publish before unsubscribe
    bus.publish(Event(EventType.POSITION_UPDATED))
    assert len(received) == 1

    # Unsubscribe
    bus.unsubscribe(token)

    # Publish after unsubscribe - should not receive
    bus.publish(Event(EventType.POSITION_UPDATED))
    assert len(received) == 1  # Still only 1


def test_event_bus_multiple_event_types():
    """Different event types are independent."""
    bus = EventBus()
    received_connection = []
    received_motion = []

    bus.subscribe(EventType.CONNECTION_SUCCEEDED, lambda e: received_connection.append(e))
    bus.subscribe(EventType.MOTION_COMPLETED, lambda e: received_motion.append(e))

    bus.publish(Event(EventType.CONNECTION_SUCCEEDED))
    bus.publish(Event(EventType.MOTION_COMPLETED))

    assert len(received_connection) == 1
    assert len(received_motion) == 1


def test_event_bus_callback_exception_handling():
    """Exception in one callback doesn't break others."""
    bus = EventBus()
    received = []

    def bad_callback(event: Event):
        raise ValueError("Intentional error")

    def good_callback(event: Event):
        received.append(event)

    bus.subscribe(EventType.ERROR_OCCURRED, bad_callback)
    bus.subscribe(EventType.ERROR_OCCURRED, good_callback)

    # Publish - bad callback raises, but good callback still runs
    bus.publish(Event(EventType.ERROR_OCCURRED))

    assert len(received) == 1  # Good callback executed


def test_event_bus_no_subscribers():
    """Publishing with no subscribers is safe."""
    bus = EventBus()

    # Should not raise
    bus.publish(Event(EventType.MOTION_STARTED))


def test_event_bus_thread_safety():
    """EventBus is thread-safe for concurrent subscribe/publish."""
    bus = EventBus()
    received = []

    def callback(event: Event):
        received.append(event)

    # Subscribe from multiple threads
    threads = []
    for i in range(10):
        t = Thread(target=lambda: bus.subscribe(EventType.STATE_CHANGED, callback))
        threads.append(t)
        t.start()

    for t in threads:
        t.join()

    # Publish from multiple threads
    threads = []
    for i in range(10):
        t = Thread(target=lambda: bus.publish(Event(EventType.STATE_CHANGED, data=i)))
        threads.append(t)
        t.start()

    for t in threads:
        t.join()

    # All events should be received (10 events * 10 subscribers = 100)
    assert len(received) == 100


def test_event_bus_clear_all():
    """clear_all removes all subscriptions."""
    bus = EventBus()
    received = []

    bus.subscribe(EventType.CONNECTION_SUCCEEDED, lambda e: received.append(e))
    bus.subscribe(EventType.MOTION_COMPLETED, lambda e: received.append(e))

    # Clear all
    bus.clear_all()

    # Publish - should not receive
    bus.publish(Event(EventType.CONNECTION_SUCCEEDED))
    bus.publish(Event(EventType.MOTION_COMPLETED))

    assert len(received) == 0


def test_event_bus_subscription_token():
    """Subscription tokens are unique."""
    bus = EventBus()

    token1 = bus.subscribe(EventType.POSITION_UPDATED, lambda e: None)
    token2 = bus.subscribe(EventType.POSITION_UPDATED, lambda e: None)

    assert token1.id != token2.id
    assert token1.event_type == EventType.POSITION_UPDATED
    assert token2.event_type == EventType.POSITION_UPDATED


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
