"""
Tests for PIAxisController with stubbed pipython.

Verifies:
- Initialization sequence (CST → SVO → reference → move off limit → VEL)
- Range clamping on moves
- Velocity clamping
- Error handling
"""

import pytest
from unittest.mock import Mock, MagicMock, patch, call
from PI_Control_System.core.models import Axis, AxisConfig, TravelRange
from PI_Control_System.core.errors import (
    ConnectionError,
    InitializationError,
    MotionError,
    CommunicationError
)
from PI_Control_System.hardware.pi_controller import PIAxisController


@pytest.fixture
def test_config():
    """Create test axis configuration."""
    return AxisConfig(
        axis=Axis.X,
        serial='TEST123',
        port='COM5',
        baud=115200,
        stage='62309260',
        refmode='FPL',
        range=TravelRange(5.0, 200.0),
        default_velocity=10.0,
        max_velocity=20.0
    )


@pytest.fixture
def mock_device():
    """Create mock GCSDevice."""
    device = MagicMock()
    device.axes = ['1']  # Single axis
    device.qIDN.return_value = "Mock PI Device"
    device.IsConnected.return_value = True
    device.qPOS.return_value = {'1': 10.0}
    device.qONT.return_value = {'1': True}
    return device


def test_pi_controller_connect(test_config, mock_device):
    """Test USB connection."""
    controller = PIAxisController(test_config)

    with patch('PI_Control_System.hardware.pi_controller.GCSDevice', return_value=mock_device):
        controller.connect()

    assert controller.is_connected
    mock_device.ConnectUSB.assert_called_once_with(serialnum='TEST123')
    mock_device.qIDN.assert_called_once()


def test_pi_controller_connect_failure(test_config):
    """Test connection failure handling."""
    controller = PIAxisController(test_config)

    mock_device = MagicMock()
    mock_device.ConnectUSB.side_effect = Exception("USB device not found")

    with patch('PI_Control_System.hardware.pi_controller.GCSDevice', return_value=mock_device):
        with pytest.raises(ConnectionError, match="Failed to connect"):
            controller.connect()

    assert not controller.is_connected


def test_pi_controller_initialize_sequence(test_config, mock_device):
    """Test 5-step initialization sequence.

    Expected order:
    1. CST (configure stage)
    2. SVO (enable servo)
    3. FPL (reference move)
    4. MVR (move off limit)
    5. VEL (set velocity)

    Source: legacy/PI_Control_GUI/hardware_controller.py:71-104
    """
    controller = PIAxisController(test_config)

    # Mock pitools.waitontarget
    with patch('PI_Control_System.hardware.pi_controller.GCSDevice', return_value=mock_device), \
         patch('PI_Control_System.hardware.pi_controller.pitools.waitontarget') as mock_wait, \
         patch('PI_Control_System.hardware.pi_controller.time.sleep'):

        controller.connect()
        controller.initialize()

    # Verify initialization sequence
    expected_calls = [
        call.CST('1', '62309260'),  # 1. Configure stage
        call.SVO('1', True),         # 2. Enable servo
        call.FPL('1'),               # 3. Reference move (config.refmode)
        call.MVR('1', -0.1),         # 4. Move off limit
        call.VEL('1', 20.0),         # 5. Set max velocity
    ]

    # Check all calls were made in order
    actual_calls = [c for c in mock_device.method_calls if c[0] in ['CST', 'SVO', 'FPL', 'MVR', 'VEL']]
    assert actual_calls == expected_calls, f"Expected {expected_calls}, got {actual_calls}"

    # Verify waitontarget called twice (after reference, after move off limit)
    assert mock_wait.call_count == 2

    assert controller.is_initialized


def test_pi_controller_initialize_without_connect(test_config):
    """Test initialization fails if not connected."""
    controller = PIAxisController(test_config)

    with pytest.raises(InitializationError, match="Not connected"):
        controller.initialize()


def test_pi_controller_move_absolute_clamping(test_config, mock_device):
    """Test absolute move with range clamping.

    Range: 5.0 - 200.0
    """
    controller = PIAxisController(test_config)

    with patch('PI_Control_System.hardware.pi_controller.GCSDevice', return_value=mock_device), \
         patch('PI_Control_System.hardware.pi_controller.pitools.waitontarget'), \
         patch('PI_Control_System.hardware.pi_controller.time.sleep'):

        controller.connect()
        controller.initialize()

        # Move within range
        mock_device.reset_mock()
        controller.move_absolute(50.0)
        mock_device.MOV.assert_called_once_with('1', 50.0)

        # Move below min (should clamp to 5.0)
        mock_device.reset_mock()
        controller.move_absolute(0.0)
        mock_device.MOV.assert_called_once_with('1', 5.0)

        # Move above max (should clamp to 200.0)
        mock_device.reset_mock()
        controller.move_absolute(250.0)
        mock_device.MOV.assert_called_once_with('1', 200.0)


def test_pi_controller_move_relative_clamping(test_config, mock_device):
    """Test relative move with range clamping."""
    controller = PIAxisController(test_config)

    # Current position at 10.0
    mock_device.qPOS.return_value = {'1': 10.0}

    with patch('PI_Control_System.hardware.pi_controller.GCSDevice', return_value=mock_device), \
         patch('PI_Control_System.hardware.pi_controller.pitools.waitontarget'), \
         patch('PI_Control_System.hardware.pi_controller.time.sleep'):

        controller.connect()
        controller.initialize()

        # Move within range
        mock_device.reset_mock()
        controller.move_relative(5.0)  # 10 + 5 = 15
        mock_device.MVR.assert_called_once_with('1', 5.0)

        # Move that would go below min
        mock_device.reset_mock()
        mock_device.qPOS.return_value = {'1': 10.0}
        controller.move_relative(-10.0)  # 10 - 10 = 0, clamped to 5
        # Actual distance should be -5.0 (10 -> 5)
        mock_device.MVR.assert_called_once_with('1', -5.0)


def test_pi_controller_velocity_clamping(test_config, mock_device):
    """Test velocity clamping to max.

    Max velocity: 20.0 mm/s
    """
    controller = PIAxisController(test_config)

    with patch('PI_Control_System.hardware.pi_controller.GCSDevice', return_value=mock_device), \
         patch('PI_Control_System.hardware.pi_controller.pitools.waitontarget'), \
         patch('PI_Control_System.hardware.pi_controller.time.sleep'):

        controller.connect()
        controller.initialize()

        # Set velocity within range
        mock_device.reset_mock()
        controller.set_velocity(15.0)
        mock_device.VEL.assert_called_once_with('1', 15.0)

        # Set velocity above max (should clamp to 20.0)
        mock_device.reset_mock()
        controller.set_velocity(25.0)
        mock_device.VEL.assert_called_once_with('1', 20.0)


def test_pi_controller_get_position(test_config, mock_device):
    """Test position query."""
    controller = PIAxisController(test_config)

    mock_device.qPOS.return_value = {'1': 42.5}

    with patch('PI_Control_System.hardware.pi_controller.GCSDevice', return_value=mock_device), \
         patch('PI_Control_System.hardware.pi_controller.pitools.waitontarget'), \
         patch('PI_Control_System.hardware.pi_controller.time.sleep'):

        controller.connect()
        controller.initialize()

        pos = controller.get_position()
        assert pos == 42.5
        mock_device.qPOS.assert_called_with('1')


def test_pi_controller_stop(test_config, mock_device):
    """Test emergency stop."""
    controller = PIAxisController(test_config)

    with patch('PI_Control_System.hardware.pi_controller.GCSDevice', return_value=mock_device), \
         patch('PI_Control_System.hardware.pi_controller.pitools.waitontarget'), \
         patch('PI_Control_System.hardware.pi_controller.time.sleep'):

        controller.connect()
        controller.initialize()

        controller.stop()
        mock_device.STP.assert_called_once()


def test_pi_controller_is_on_target(test_config, mock_device):
    """Test on-target query."""
    controller = PIAxisController(test_config)

    mock_device.qONT.return_value = {'1': True}

    with patch('PI_Control_System.hardware.pi_controller.GCSDevice', return_value=mock_device), \
         patch('PI_Control_System.hardware.pi_controller.pitools.waitontarget'), \
         patch('PI_Control_System.hardware.pi_controller.time.sleep'):

        controller.connect()
        controller.initialize()

        assert controller.is_on_target() == True

        mock_device.qONT.return_value = {'1': False}
        assert controller.is_on_target() == False


def test_pi_controller_wait_for_target(test_config, mock_device):
    """Test blocking wait."""
    controller = PIAxisController(test_config)

    with patch('PI_Control_System.hardware.pi_controller.GCSDevice', return_value=mock_device), \
         patch('PI_Control_System.hardware.pi_controller.pitools.waitontarget') as mock_wait, \
         patch('PI_Control_System.hardware.pi_controller.time.sleep'):

        controller.connect()
        controller.initialize()

        mock_wait.reset_mock()
        controller.wait_for_target(timeout=5.0)
        mock_wait.assert_called_once_with(mock_device, timeout=5.0)


def test_pi_controller_disconnect(test_config, mock_device):
    """Test disconnect cleanup."""
    controller = PIAxisController(test_config)

    with patch('PI_Control_System.hardware.pi_controller.GCSDevice', return_value=mock_device):
        controller.connect()
        assert controller.is_connected

        controller.disconnect()
        assert not controller.is_connected
        mock_device.CloseConnection.assert_called_once()


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
