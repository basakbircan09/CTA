"""
Test immutability guarantees for frozen dataclasses.
"""

from dataclasses import FrozenInstanceError

import pytest

from PI_Control_System.core.models import Position, SequenceConfig, Waypoint


def test_position_frozen():
    """Position should be immutable."""
    pos = Position(10.0, 20.0, 30.0)

    with pytest.raises(FrozenInstanceError):
        pos.x = 50.0


def test_waypoint_frozen():
    """Waypoint should be immutable."""
    wp = Waypoint(Position(10.0, 20.0, 30.0), 1.0)

    with pytest.raises(FrozenInstanceError):
        wp.hold_time = 2.0


def test_sequence_config_frozen():
    """SequenceConfig should be immutable."""
    config = SequenceConfig(
        waypoints=(Waypoint(Position(10.0, 20.0, 30.0), 1.0),),
        park_when_complete=True,
    )

    with pytest.raises(FrozenInstanceError):
        config.park_when_complete = False
