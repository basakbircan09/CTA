"""
Unit tests for core models.

Verifies immutability, clamping logic, and dict compatibility.
"""

from PI_Control_System.core.models import (
    Axis, Position, TravelRange, AxisConfig, Waypoint, ConnectionState
)


def test_position_immutability():
    """Position should be immutable."""
    pos = Position(10.0, 20.0, 30.0)
    new_pos = pos.with_axis(Axis.X, 50.0)

    assert pos.x == 10.0  # Original unchanged
    assert new_pos.x == 50.0
    assert new_pos.y == 20.0
    assert new_pos.z == 30.0


def test_position_dict_access():
    """Position should support dict-like access."""
    pos = Position(10.0, 20.0, 30.0)

    assert pos[Axis.X] == 10.0
    assert pos[Axis.Y] == 20.0
    assert pos[Axis.Z] == 30.0


def test_travel_range_clamp():
    """TravelRange should clamp values correctly.

    Source: origintools.py:21-34
    """
    range = TravelRange(5.0, 200.0)

    assert range.clamp(3.0) == 5.0      # Below min
    assert range.clamp(250.0) == 200.0  # Above max
    assert range.clamp(100.0) == 100.0  # Within range


def test_travel_range_contains():
    """TravelRange should check containment."""
    range = TravelRange(5.0, 200.0)

    assert not range.contains(3.0)
    assert range.contains(5.0)
    assert range.contains(100.0)
    assert range.contains(200.0)
    assert not range.contains(201.0)


def test_waypoint_from_dict():
    """Waypoint should convert from legacy dict format.

    Source: config.py:53-56
    """
    legacy_data = {'X': 10.0, 'Y': 5.0, 'Z': 20.0, 'holdTime': 1.0}
    wp = Waypoint.from_dict(legacy_data)

    assert wp.position.x == 10.0
    assert wp.position.y == 5.0
    assert wp.position.z == 20.0
    assert wp.hold_time == 1.0


def test_axis_enum():
    """Axis enum should be string-based."""
    assert Axis.X.value == "X"
    assert Axis.Y.value == "Y"
    assert Axis.Z.value == "Z"


def test_connection_state_enum():
    """ConnectionState should have all required states."""
    states = {s.value for s in ConnectionState}
    required = {"disconnected", "connecting", "connected", "initializing", "ready", "error"}
    assert states == required


if __name__ == '__main__':
    # Run tests
    test_position_immutability()
    test_position_dict_access()
    test_travel_range_clamp()
    test_travel_range_contains()
    test_waypoint_from_dict()
    test_axis_enum()
    test_connection_state_enum()

    print("✓ All model tests passed")
