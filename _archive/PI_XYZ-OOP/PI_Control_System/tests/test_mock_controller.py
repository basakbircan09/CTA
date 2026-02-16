"""
Tests for mock axis controller.
"""

import pytest
from PI_Control_System.core.models import Axis, AxisConfig, TravelRange
from PI_Control_System.core.errors import ConnectionError, InitializationError
from PI_Control_System.hardware.mock_controller import MockAxisController


@pytest.fixture
def test_config():
    """Create test axis configuration."""
    return AxisConfig(
        axis=Axis.X,
        serial='TEST123',
        port='COM99',
        baud=115200,
        stage='TEST_STAGE',
        refmode='FPL',
        range=TravelRange(5.0, 200.0),
        default_velocity=10.0,
        max_velocity=20.0
    )


def test_mock_lifecycle(test_config):
    """Test connection/initialization lifecycle."""
    controller = MockAxisController(test_config)

    # Initial state
    assert not controller.is_connected
    assert not controller.is_initialized

    # Connect
    controller.connect()
    assert controller.is_connected
    assert not controller.is_initialized

    # Initialize
    controller.initialize()
    assert controller.is_connected
    assert controller.is_initialized

    # Position should be at range min after init
    assert controller.get_position() == test_config.range.min

    # Disconnect
    controller.disconnect()
    assert not controller.is_connected
    assert not controller.is_initialized


def test_mock_move_absolute(test_config):
    """Test absolute motion."""
    controller = MockAxisController(test_config)
    controller.connect()
    controller.initialize()

    # Move to position
    controller.move_absolute(50.0)
    assert controller.is_on_target() == False  # Moving

    controller.wait_for_target()
    assert controller.get_position() == 50.0
    assert controller.is_on_target() == True


def test_mock_move_relative(test_config):
    """Test relative motion."""
    controller = MockAxisController(test_config)
    controller.connect()
    controller.initialize()

    initial = controller.get_position()

    # Move relative
    controller.move_relative(10.0)
    controller.wait_for_target()

    assert controller.get_position() == initial + 10.0


def test_mock_range_clamping(test_config):
    """Test position clamping to range."""
    controller = MockAxisController(test_config)
    controller.connect()
    controller.initialize()

    # Try to move below min
    controller.move_absolute(0.0)  # Below min of 5.0
    controller.wait_for_target()
    assert controller.get_position() == 5.0

    # Try to move above max
    controller.move_absolute(250.0)  # Above max of 200.0
    controller.wait_for_target()
    assert controller.get_position() == 200.0


def test_mock_velocity(test_config):
    """Test velocity management."""
    controller = MockAxisController(test_config)
    controller.connect()
    controller.initialize()

    # Set velocity within range
    controller.set_velocity(15.0)
    # MockAxisController doesn't expose velocity getter, but shouldn't raise

    # Set above max - should clamp internally
    controller.set_velocity(25.0)  # Above max of 20.0


def test_mock_stop(test_config):
    """Test emergency stop."""
    controller = MockAxisController(test_config, motion_delay=0.1)
    controller.connect()
    controller.initialize()

    # Start move
    controller.move_absolute(100.0)
    assert not controller.is_on_target()

    # Stop before completion
    controller.stop()
    assert controller.is_on_target()


def test_mock_init_without_connect(test_config):
    """Test initialization fails if not connected."""
    controller = MockAxisController(test_config)

    with pytest.raises(InitializationError):
        controller.initialize()


def test_mock_move_without_init(test_config):
    """Test move fails if not initialized."""
    controller = MockAxisController(test_config)
    controller.connect()

    with pytest.raises(InitializationError):
        controller.move_absolute(50.0)


def test_mock_fail_on_connect(test_config):
    """Test controllable connection failure."""
    controller = MockAxisController(test_config, fail_on_connect=True)

    with pytest.raises(ConnectionError):
        controller.connect()


def test_mock_fail_on_initialize(test_config):
    """Test controllable initialization failure."""
    controller = MockAxisController(test_config, fail_on_initialize=True)
    controller.connect()

    with pytest.raises(InitializationError):
        controller.initialize()


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
