"""
Tests for ConnectionService.

Verifies:
- State machine transitions
- Event publishing
- Async operation coordination
- Error handling
"""

import pytest
from concurrent.futures import ThreadPoolExecutor
from PI_Control_System.core.models import Axis, AxisConfig, TravelRange, ConnectionState, InitializationState
from PI_Control_System.core.errors import InitializationError
from PI_Control_System.hardware.mock_controller import MockAxisController
from PI_Control_System.hardware.pi_manager import PIControllerManager
from PI_Control_System.services.event_bus import EventBus, EventType
from PI_Control_System.services.connection_service import ConnectionService


@pytest.fixture
def test_configs():
    """Create test configurations."""
    return {
        Axis.X: AxisConfig(Axis.X, 'X', 'COM1', 115200, 'TEST', 'FPL',
                          TravelRange(5.0, 200.0), 10.0, 20.0),
        Axis.Y: AxisConfig(Axis.Y, 'Y', 'COM2', 115200, 'TEST', 'FPL',
                          TravelRange(0.0, 200.0), 10.0, 20.0),
        Axis.Z: AxisConfig(Axis.Z, 'Z', 'COM3', 115200, 'TEST', 'FPL',
                          TravelRange(15.0, 200.0), 10.0, 20.0),
    }


@pytest.fixture
def mock_manager(test_configs):
    """Create manager with mock controllers."""
    controllers = {
        axis: MockAxisController(config)
        for axis, config in test_configs.items()
    }
    return PIControllerManager(controllers)


@pytest.fixture
def event_bus():
    """Create event bus."""
    return EventBus()


@pytest.fixture
def executor():
    """Create thread pool executor."""
    ex = ThreadPoolExecutor(max_workers=2)
    yield ex
    ex.shutdown(wait=True)


def test_connection_service_initial_state(mock_manager, event_bus, executor):
    """Service should start in DISCONNECTED state."""
    service = ConnectionService(mock_manager, event_bus, executor)

    state = service.state
    assert state.connection == ConnectionState.DISCONNECTED
    assert state.initialization == InitializationState.NOT_INITIALIZED
    assert not service.is_ready()


def test_connection_service_connect_success(mock_manager, event_bus, executor):
    """Successful connection should publish events and update state."""
    service = ConnectionService(mock_manager, event_bus, executor)

    # Track events
    events = []
    event_bus.subscribe(EventType.CONNECTION_STARTED, lambda e: events.append(e))
    event_bus.subscribe(EventType.CONNECTION_SUCCEEDED, lambda e: events.append(e))
    event_bus.subscribe(EventType.STATE_CHANGED, lambda e: events.append(e))

    # Connect
    future = service.connect()
    future.result()  # Wait for completion

    # Check events published
    assert any(e.event_type == EventType.CONNECTION_STARTED for e in events)
    assert any(e.event_type == EventType.CONNECTION_SUCCEEDED for e in events)
    assert any(e.event_type == EventType.STATE_CHANGED for e in events)

    # Check state
    assert service.state.connection == ConnectionState.CONNECTED
    assert not service.is_ready()  # Not ready until initialized


def test_connection_service_connect_failure(test_configs, event_bus, executor):
    """Failed connection should publish error events."""
    # Create manager with controller that fails on connect
    controllers = {
        Axis.X: MockAxisController(test_configs[Axis.X], fail_on_connect=True),
        Axis.Y: MockAxisController(test_configs[Axis.Y]),
        Axis.Z: MockAxisController(test_configs[Axis.Z]),
    }
    manager = PIControllerManager(controllers)
    service = ConnectionService(manager, event_bus, executor)

    # Track events
    events = []
    event_bus.subscribe(EventType.CONNECTION_FAILED, lambda e: events.append(e))
    event_bus.subscribe(EventType.ERROR_OCCURRED, lambda e: events.append(e))

    # Connect
    future = service.connect()

    try:
        future.result()
        assert False, "Should have raised ConnectionError"
    except Exception:
        pass  # Expected

    # Check error events published
    assert any(e.event_type == EventType.CONNECTION_FAILED for e in events)
    assert any(e.event_type == EventType.ERROR_OCCURRED for e in events)

    # Check state
    assert service.state.connection == ConnectionState.ERROR


def test_connection_service_initialize_success(mock_manager, event_bus, executor):
    """Successful initialization should publish events and update state."""
    service = ConnectionService(mock_manager, event_bus, executor)

    # Track events
    events = []
    event_bus.subscribe(EventType.INITIALIZATION_STARTED, lambda e: events.append(e))
    event_bus.subscribe(EventType.INITIALIZATION_SUCCEEDED, lambda e: events.append(e))
    event_bus.subscribe(EventType.STATE_CHANGED, lambda e: events.append(e))

    # Connect and initialize
    service.connect().result()
    future = service.initialize()
    future.result()

    # Check events
    assert any(e.event_type == EventType.INITIALIZATION_STARTED for e in events)
    assert any(e.event_type == EventType.INITIALIZATION_SUCCEEDED for e in events)

    # Check state
    assert service.state.connection == ConnectionState.READY
    assert service.state.initialization == InitializationState.INITIALIZED
    assert service.is_ready()


def test_connection_service_initialize_without_connect(mock_manager, event_bus, executor):
    """Initialize should fail if not connected."""
    service = ConnectionService(mock_manager, event_bus, executor)

    with pytest.raises(InitializationError, match="not connected"):
        service.initialize()


def test_connection_service_initialize_failure(test_configs, event_bus, executor):
    """Failed initialization should publish error events."""
    # Create manager with controller that fails on initialize
    controllers = {
        Axis.X: MockAxisController(test_configs[Axis.X]),
        Axis.Y: MockAxisController(test_configs[Axis.Y], fail_on_initialize=True),
        Axis.Z: MockAxisController(test_configs[Axis.Z]),
    }
    manager = PIControllerManager(controllers)
    service = ConnectionService(manager, event_bus, executor)

    # Track events
    events = []
    event_bus.subscribe(EventType.INITIALIZATION_FAILED, lambda e: events.append(e))
    event_bus.subscribe(EventType.ERROR_OCCURRED, lambda e: events.append(e))

    # Connect then try initialize
    service.connect().result()
    future = service.initialize()

    try:
        future.result()
        assert False, "Should have raised InitializationError"
    except Exception:
        pass  # Expected

    # Check error events
    assert any(e.event_type == EventType.INITIALIZATION_FAILED for e in events)
    assert any(e.event_type == EventType.ERROR_OCCURRED for e in events)

    # Check state
    assert service.state.connection == ConnectionState.ERROR
    assert service.state.initialization == InitializationState.FAILED


def test_connection_service_disconnect(mock_manager, event_bus, executor):
    """Disconnect should cleanup and update state."""
    service = ConnectionService(mock_manager, event_bus, executor)

    # Track events
    events = []
    event_bus.subscribe(EventType.STATE_CHANGED, lambda e: events.append(e))

    # Connect, initialize, then disconnect
    service.connect().result()
    service.initialize().result()

    assert service.is_ready()

    service.disconnect()

    # Check state reset
    assert service.state.connection == ConnectionState.DISCONNECTED
    assert service.state.initialization == InitializationState.NOT_INITIALIZED
    assert not service.is_ready()


def test_connection_service_full_lifecycle(mock_manager, event_bus, executor):
    """Test complete connect → initialize → disconnect lifecycle."""
    service = ConnectionService(mock_manager, event_bus, executor)

    # Track all events
    events = []
    for event_type in EventType:
        event_bus.subscribe(event_type, lambda e: events.append(e))

    # Full lifecycle
    service.connect().result()
    assert service.state.connection == ConnectionState.CONNECTED

    service.initialize().result()
    assert service.is_ready()

    service.disconnect()
    assert not service.is_ready()

    # Verify event sequence
    event_types = [e.event_type for e in events]
    assert EventType.CONNECTION_STARTED in event_types
    assert EventType.CONNECTION_SUCCEEDED in event_types
    assert EventType.INITIALIZATION_STARTED in event_types
    assert EventType.INITIALIZATION_SUCCEEDED in event_types


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
