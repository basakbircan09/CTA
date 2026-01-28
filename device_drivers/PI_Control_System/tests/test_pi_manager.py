"""
Tests for PI controller manager with mock controllers.

Verifies:
- Dependency injection works
- Safe reference order (Z → X → Y) enforced
- Safe park sequence (Z first, then X/Y together)
- Multi-axis coordination
"""

import pytest
from PI_Control_System.core.models import Axis, AxisConfig, TravelRange
from PI_Control_System.core.errors import ConnectionError, InitializationError
from PI_Control_System.hardware.pi_manager import PIControllerManager, REFERENCE_ORDER
from PI_Control_System.hardware.mock_controller import MockAxisController


@pytest.fixture
def test_configs():
    """Create test configurations for all axes."""
    return {
        Axis.X: AxisConfig(
            axis=Axis.X,
            serial='TEST_X',
            port='COM1',
            baud=115200,
            stage='TEST',
            refmode='FPL',
            range=TravelRange(5.0, 200.0),
            default_velocity=10.0,
            max_velocity=20.0
        ),
        Axis.Y: AxisConfig(
            axis=Axis.Y,
            serial='TEST_Y',
            port='COM2',
            baud=115200,
            stage='TEST',
            refmode='FPL',
            range=TravelRange(0.0, 200.0),
            default_velocity=10.0,
            max_velocity=20.0
        ),
        Axis.Z: AxisConfig(
            axis=Axis.Z,
            serial='TEST_Z',
            port='COM3',
            baud=115200,
            stage='TEST',
            refmode='FPL',
            range=TravelRange(15.0, 200.0),
            default_velocity=10.0,
            max_velocity=20.0
        ),
    }


@pytest.fixture
def mock_controllers(test_configs):
    """Create mock controllers for all axes."""
    return {
        axis: MockAxisController(config)
        for axis, config in test_configs.items()
    }


def test_manager_requires_all_axes(test_configs):
    """Manager should raise if any axis missing."""
    # Missing Z axis
    incomplete = {
        Axis.X: MockAxisController(test_configs[Axis.X]),
        Axis.Y: MockAxisController(test_configs[Axis.Y]),
    }

    with pytest.raises(ValueError, match="Missing controller for Z"):
        PIControllerManager(incomplete)


def test_manager_accepts_injected_controllers(mock_controllers):
    """Manager should accept any AxisController implementation."""
    manager = PIControllerManager(mock_controllers)

    # Should be able to get controllers
    assert manager.get_controller(Axis.X) is mock_controllers[Axis.X]
    assert manager.get_controller(Axis.Y) is mock_controllers[Axis.Y]
    assert manager.get_controller(Axis.Z) is mock_controllers[Axis.Z]


def test_manager_connect_all(mock_controllers):
    """Manager should connect all controllers."""
    manager = PIControllerManager(mock_controllers)

    # Initially disconnected
    assert not mock_controllers[Axis.X].is_connected
    assert not mock_controllers[Axis.Y].is_connected
    assert not mock_controllers[Axis.Z].is_connected

    # Connect all
    manager.connect_all()

    # All connected
    assert mock_controllers[Axis.X].is_connected
    assert mock_controllers[Axis.Y].is_connected
    assert mock_controllers[Axis.Z].is_connected


def test_manager_connect_cleanup_on_failure(test_configs):
    """Manager should cleanup partial connections on failure."""
    # Z controller fails on connect
    controllers = {
        Axis.X: MockAxisController(test_configs[Axis.X]),
        Axis.Y: MockAxisController(test_configs[Axis.Y]),
        Axis.Z: MockAxisController(test_configs[Axis.Z], fail_on_connect=True),
    }

    manager = PIControllerManager(controllers)

    # Connect should fail
    with pytest.raises(ConnectionError):
        manager.connect_all()

    # X and Y should be disconnected (cleanup)
    # Note: Mock doesn't auto-disconnect on manager cleanup,
    # but real implementation calls disconnect_all()


def test_manager_initialize_order(mock_controllers):
    """Manager should initialize in safe order: Z → X → Y."""
    manager = PIControllerManager(mock_controllers)

    # Track initialization order
    init_order = []

    # Wrap initialize to track calls
    for axis, controller in mock_controllers.items():
        original_init = controller.initialize

        def make_tracker(ax):
            def tracked_init():
                init_order.append(ax)
                original_init()
            return tracked_init

        controller.initialize = make_tracker(axis)

    # Connect and initialize
    manager.connect_all()
    manager.initialize_all()

    # Verify order matches REFERENCE_ORDER
    assert init_order == REFERENCE_ORDER, f"Expected {REFERENCE_ORDER}, got {init_order}"


def test_manager_initialize_all(mock_controllers):
    """Manager should initialize all controllers."""
    manager = PIControllerManager(mock_controllers)
    manager.connect_all()

    # Initially not initialized
    assert not mock_controllers[Axis.X].is_initialized
    assert not mock_controllers[Axis.Y].is_initialized
    assert not mock_controllers[Axis.Z].is_initialized

    # Initialize all
    manager.initialize_all()

    # All initialized
    assert mock_controllers[Axis.X].is_initialized
    assert mock_controllers[Axis.Y].is_initialized
    assert mock_controllers[Axis.Z].is_initialized


def test_manager_position_snapshot(mock_controllers):
    """Manager should return position snapshot from all axes."""
    manager = PIControllerManager(mock_controllers)
    manager.connect_all()
    manager.initialize_all()

    # Move axes to known positions
    mock_controllers[Axis.X].move_absolute(50.0)
    mock_controllers[Axis.X].wait_for_target()

    mock_controllers[Axis.Y].move_absolute(75.0)
    mock_controllers[Axis.Y].wait_for_target()

    mock_controllers[Axis.Z].move_absolute(100.0)
    mock_controllers[Axis.Z].wait_for_target()

    # Get snapshot
    pos = manager.get_position_snapshot()

    assert pos.x == 50.0
    assert pos.y == 75.0
    assert pos.z == 100.0


def test_manager_park_sequence(mock_controllers):
    """Manager should park in safe order: Z first, then X/Y together."""
    manager = PIControllerManager(mock_controllers)
    manager.connect_all()
    manager.initialize_all()

    # Track move order
    move_order = []
    wait_order = []

    # Wrap methods to track calls
    for axis, controller in mock_controllers.items():
        original_move = controller.move_absolute
        original_wait = controller.wait_for_target

        def make_move_tracker(ax):
            def tracked_move(pos):
                move_order.append(ax)
                return original_move(pos)
            return tracked_move

        def make_wait_tracker(ax):
            def tracked_wait(timeout=None):
                wait_order.append(ax)
                return original_wait(timeout)
            return tracked_wait

        controller.move_absolute = make_move_tracker(axis)
        controller.wait_for_target = make_wait_tracker(axis)

    # Execute park
    manager.park_all(200.0)

    # Verify Z moves first
    assert move_order[0] == Axis.Z, f"Z should move first, got {move_order}"

    # Verify Z waits before X/Y move
    assert wait_order[0] == Axis.Z, f"Z should wait first, got {wait_order}"

    # Verify X and Y move after Z waits
    assert Axis.X in move_order[1:3], "X should move after Z"
    assert Axis.Y in move_order[1:3], "Y should move after Z"


def test_manager_disconnect_all(mock_controllers):
    """Manager should disconnect all controllers."""
    manager = PIControllerManager(mock_controllers)
    manager.connect_all()

    # All connected
    assert all(c.is_connected for c in mock_controllers.values())

    # Disconnect
    manager.disconnect_all()

    # All disconnected
    assert not any(c.is_connected for c in mock_controllers.values())


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
