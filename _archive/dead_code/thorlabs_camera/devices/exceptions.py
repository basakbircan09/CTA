"""
Custom exceptions raised by the Thorlabs device layer.

Wrapping pylablib/runtime failures in these domain-specific types keeps
upper layers independent from the underlying SDK and simplifies testing.
"""

from __future__ import annotations


class CameraError(Exception):
    """Base exception for all camera-related failures."""


class CameraConnectionError(CameraError):
    """Raised when the camera cannot be discovered or opened."""


class CameraConfigurationError(CameraError):
    """Raised when applying settings to the camera fails."""


class AcquisitionError(CameraError):
    """Raised when starting or stopping acquisition encounters an error."""


class FrameTimeoutError(CameraError):
    """Raised when a frame is not received within the expected time window."""


class SnapshotError(CameraError):
    """Raised when saving or processing a captured frame fails."""

