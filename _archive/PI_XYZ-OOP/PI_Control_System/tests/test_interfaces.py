"""
Tests for hardware interface contracts.
"""

from abc import ABC
from PI_Control_System.core.hardware.interfaces import AxisController, AxisControllerManager


def test_axis_controller_is_abstract():
    """AxisController should be abstract."""
    assert issubclass(AxisController, ABC)

    # Cannot instantiate directly
    try:
        controller = AxisController()
        assert False, "Should not be able to instantiate abstract class"
    except TypeError:
        pass  # Expected


def test_axis_controller_manager_is_abstract():
    """AxisControllerManager should be abstract."""
    assert issubclass(AxisControllerManager, ABC)

    try:
        manager = AxisControllerManager()
        assert False, "Should not be able to instantiate abstract class"
    except TypeError:
        pass  # Expected


if __name__ == '__main__':
    test_axis_controller_is_abstract()
    test_axis_controller_manager_is_abstract()
    print("✓ All interface tests passed")
