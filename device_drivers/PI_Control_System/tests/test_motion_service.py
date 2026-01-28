"""
Tests for MotionService orchestration.
"""

import time
from concurrent.futures import ThreadPoolExecutor
from typing import Dict

import pytest

from PI_Control_System.core.errors import MotionError
from PI_Control_System.core.hardware.interfaces import AxisControllerManager
from PI_Control_System.core.models import Axis, AxisConfig, Position, SequenceConfig, TravelRange, Waypoint
from PI_Control_System.hardware.mock_controller import MockAxisController
from PI_Control_System.services.connection_service import ConnectionService
from PI_Control_System.services.event_bus import EventBus, EventType
from PI_Control_System.services.motion_service import MotionService
from unittest.mock import MagicMock
import threading


class DummyManager(AxisControllerManager):
    """Test double that wraps injected controllers."""

    def __init__(self, controllers: Dict[Axis, MockAxisController]):
        self.controllers = controllers
        self.park_calls = []

    def connect_all(self) -> None:
        for controller in self.controllers.values():
            controller.connect()

    def disconnect_all(self) -> None:
        for controller in self.controllers.values():
            controller.disconnect()

    def initialize_all(self) -> None:
        for controller in self.controllers.values():
            controller.initialize()

    def get_controller(self, axis: Axis):
        return self.controllers[axis]

    def get_position_snapshot(self) -> Position:
        return Position(
            x=self.controllers[Axis.X].get_position(),
            y=self.controllers[Axis.Y].get_position(),
            z=self.controllers[Axis.Z].get_position(),
        )

    def park_all(self, position: float) -> None:
        self.park_calls.append(position)
        # mimic safe sequence: Z first, then X/Y
        order = [Axis.Z, Axis.X, Axis.Y]
        for axis in order:
            controller = self.controllers[axis]
            controller.move_absolute(position)
            controller.wait_for_target()


@pytest.fixture
def test_configs():
    """Sample axis configs."""
    return {
        Axis.X: AxisConfig(
            axis=Axis.X,
            serial="TEST_X",
            port="COM1",
            baud=115200,
            stage="TEST",
            refmode="FPL",
            range=TravelRange(5.0, 200.0),
            default_velocity=10.0,
            max_velocity=20.0,
        ),
        Axis.Y: AxisConfig(
            axis=Axis.Y,
            serial="TEST_Y",
            port="COM2",
            baud=115200,
            stage="TEST",
            refmode="FPL",
            range=TravelRange(0.0, 200.0),
            default_velocity=10.0,
            max_velocity=20.0,
        ),
        Axis.Z: AxisConfig(
            axis=Axis.Z,
            serial="TEST_Z",
            port="COM3",
            baud=115200,
            stage="TEST",
            refmode="FPL",
            range=TravelRange(15.0, 200.0),
            default_velocity=10.0,
            max_velocity=20.0,
        ),
    }


@pytest.fixture
def controllers(test_configs):
    """Create initialized mock controllers."""
    ctrls = {
        axis: MockAxisController(config, motion_delay=0.01)
        for axis, config in test_configs.items()
    }
    manager = DummyManager(ctrls)
    manager.connect_all()
    manager.initialize_all()
    return ctrls, manager


@pytest.fixture
def event_bus():
    return EventBus()


@pytest.fixture
def executor():
    pool = ThreadPoolExecutor(max_workers=4)
    try:
        yield pool
    finally:
        pool.shutdown(wait=True)


@pytest.fixture
def motion_service(controllers, event_bus, executor):
    ctrls, manager = controllers
    connection_service = MagicMock(spec=ConnectionService)
    service = MotionService(
        controller_manager=manager,
        event_bus=event_bus,
        executor=executor,
        connection_service=connection_service,
    )
    return service, ctrls, manager, event_bus


def collect_events(event_bus: EventBus, event_type: EventType):
    events = []
    token = event_bus.subscribe(event_type, lambda event: events.append(event))
    return events, token


def test_move_axis_absolute(motion_service):
    service, controllers, _, event_bus = motion_service
    events, token = collect_events(event_bus, EventType.MOTION_PROGRESS)

    future = service.move_axis_absolute(Axis.X, 50.0)
    future.result(timeout=1)

    assert controllers[Axis.X].get_position() == 50.0
    assert events and "X" in events[0].data
    event_bus.unsubscribe(token)


def test_move_axis_relative(motion_service):
    service, controllers, _, event_bus = motion_service
    events, token = collect_events(event_bus, EventType.MOTION_PROGRESS)

    future = service.move_axis_relative(Axis.X, 5.0)
    future.result(timeout=1)

    assert controllers[Axis.X].get_position() == controllers[Axis.X].config.range.min + 5.0
    assert events and "+=" in events[0].data
    event_bus.unsubscribe(token)


def test_move_to_position_wait_false(motion_service):
    service, controllers, _, _ = motion_service

    target = Position(20.0, 30.0, 40.0)
    future = service.move_to_position(target, wait=False)
    future.result(timeout=1)

    # Without wait, position remains at initial clamp
    assert controllers[Axis.X].get_position() != 20.0
    assert not controllers[Axis.X].is_on_target()


def test_move_to_position_wait_true(motion_service):
    service, controllers, _, _ = motion_service

    target = Position(25.0, 35.0, 45.0)
    future = service.move_to_position(target)
    future.result(timeout=1)

    assert controllers[Axis.X].get_position() == 25.0
    assert controllers[Axis.Y].get_position() == 35.0
    assert controllers[Axis.Z].get_position() == 45.0


def test_sequence_executes_and_parks(motion_service):
    service, controllers, manager, event_bus = motion_service
    events, token = collect_events(event_bus, EventType.MOTION_PROGRESS)

    sequence = SequenceConfig(
        waypoints=(
            Waypoint(Position(30.0, 40.0, 50.0), hold_time=0.0),
            Waypoint(Position(60.0, 70.0, 80.0), hold_time=0.0),
        ),
        park_when_complete=True,
        park_position=100.0,
    )

    future = service.execute_sequence(sequence)
    future.result(timeout=2)

    # Verify waypoints visited and park executed
    assert controllers[Axis.X].get_position() == 100.0
    assert controllers[Axis.Y].get_position() == 100.0
    assert controllers[Axis.Z].get_position() == 100.0
    assert manager.park_calls == [100.0]
    assert len(events) == 2
    event_bus.unsubscribe(token)


def test_sequence_cancellation(motion_service):
    service, controllers, _, event_bus = motion_service
    cancel_event = threading.Event()
    token = event_bus.subscribe(EventType.MOTION_FAILED, lambda _: cancel_event.set())

    sequence = SequenceConfig(
        waypoints=(
            Waypoint(Position(50.0, 50.0, 50.0), hold_time=0.5),
        ),
        park_when_complete=False,
    )

    future = service.execute_sequence(sequence)
    time.sleep(0.1)
    service.cancel_motion()

    with pytest.raises(MotionError):
        future.result(timeout=2)

    assert cancel_event.wait(timeout=1.0)
    event_bus.unsubscribe(token)


def test_park_all(motion_service):
    service, _, manager, _ = motion_service
    future = service.park_all(150.0)
    future.result(timeout=1)
    assert manager.park_calls == [150.0]


def test_move_error_publishes_event(motion_service):
    service, controllers, _, event_bus = motion_service

    class FailingController(MockAxisController):
        def move_absolute(self, position: float) -> None:
            raise MotionError("boom")

    controllers[Axis.X] = FailingController(controllers[Axis.X].config)
    controllers[Axis.X].connect()
    controllers[Axis.X].initialize()

    events, token = collect_events(event_bus, EventType.ERROR_OCCURRED)
    future = service.move_axis_absolute(Axis.X, 20.0)

    with pytest.raises(MotionError):
        future.result(timeout=1)

    assert events and "boom" in events[0].data
    event_bus.unsubscribe(token)
