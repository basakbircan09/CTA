"""
Exception hierarchy for PI stage control system.

Typed exceptions enable targeted error handling at service and GUI layers.
"""


class PIControlError(Exception):
    """Base exception for all PI control system errors."""
    pass


class ConfigurationError(PIControlError):
    """Invalid or missing configuration data.

    Raised during config load when:
    - Required fields are missing
    - Values are out of valid range
    - Schema validation fails
    """
    pass


class ConnectionError(PIControlError):
    """Hardware connection failure.

    Raised by AxisController.connect() when:
    - USB device not found
    - Serial communication fails
    - Device identification fails

    Source: hardware_controller.py:35-57 (connection logic)
    """
    pass


class InitializationError(PIControlError):
    """Reference sequence failure.

    Raised by AxisController.initialize() when:
    - Stage configuration fails
    - Servo enable fails
    - Reference move fails
    - Timeout during initialization

    Source: hardware_controller.py:59-120 (initialization sequence)
    """
    pass


class MotionError(PIControlError):
    """Move command failure or range violation.

    Raised by AxisController.move_* methods when:
    - Motion command fails
    - Target out of safe range (after clamping)
    - Axis not initialized
    - Hardware communication error during move

    Source: hardware_controller.py:152-205 (move commands)
    """
    pass


class CommunicationError(PIControlError):
    """Hardware communication error.

    Raised during queries when:
    - Position read fails
    - Velocity set fails
    - Status query fails

    Source: hardware_controller.py:225-243 (position queries)
    """
    pass
