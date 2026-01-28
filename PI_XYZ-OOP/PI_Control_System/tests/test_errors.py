"""
Unit tests for exception hierarchy.
"""

from PI_Control_System.core.errors import (
    PIControlError,
    ConfigurationError,
    ConnectionError,
    InitializationError,
    MotionError,
    CommunicationError
)


def test_exception_hierarchy():
    """All exceptions should inherit from PIControlError."""
    exceptions = [
        ConfigurationError,
        ConnectionError,
        InitializationError,
        MotionError,
        CommunicationError
    ]

    for exc_class in exceptions:
        assert issubclass(exc_class, PIControlError)
        assert issubclass(exc_class, Exception)


def test_exception_raising():
    """Exceptions should be raisable with messages."""
    try:
        raise ConnectionError("Test connection failure")
    except PIControlError as e:
        assert str(e) == "Test connection failure"
        assert isinstance(e, ConnectionError)


def test_exception_catching():
    """Should be able to catch specific or base exception."""
    # Catch specific
    try:
        raise MotionError("Move failed")
    except MotionError as e:
        assert "Move failed" in str(e)

    # Catch base class
    try:
        raise InitializationError("Init failed")
    except PIControlError as e:
        assert isinstance(e, InitializationError)


if __name__ == '__main__':
    test_exception_hierarchy()
    test_exception_raising()
    test_exception_catching()

    print("✓ All exception tests passed")
