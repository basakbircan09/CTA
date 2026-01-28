"""
Core data models for PI stage control system.

All models are immutable where possible for thread safety.
Source references point to master branch files.
"""

from dataclasses import dataclass
from enum import Enum
from typing import Literal


# ============================================================================
# Enumerations
# ============================================================================

class Axis(str, Enum):
    """Stage axis identifiers.

    Source: config.py:11-35 (CONTROLLER_CONFIG keys)
    """
    X = "X"
    Y = "Y"
    Z = "Z"


class ConnectionState(Enum):
    """Hardware connection state machine.

    Source: main_gui.py:520-613 (button enable/disable logic)
    """
    DISCONNECTED = "disconnected"
    CONNECTING = "connecting"
    CONNECTED = "connected"
    INITIALIZING = "initializing"
    READY = "ready"
    ERROR = "error"


class InitializationState(Enum):
    """Initialization/referencing state."""
    NOT_INITIALIZED = "not_initialized"
    INITIALIZING = "initializing"
    INITIALIZED = "initialized"
    FAILED = "failed"


# ============================================================================
# Core Data Structures
# ============================================================================

@dataclass(frozen=True)
class TravelRange:
    """Physical travel limits for a single axis in mm.

    Source: origintools.py:16-33 (safe_range function)
    """
    min: float
    max: float

    def clamp(self, value: float) -> float:
        """Clamp value to range.

        Source: origintools.py:21-34
        """
        if value < self.min:
            return self.min
        if value > self.max:
            return self.max
        return value

    def contains(self, value: float) -> bool:
        """Check if value is within range."""
        return self.min <= value <= self.max


@dataclass(frozen=True)
class AxisConfig:
    """Hardware configuration for a single axis.

    Source: config.py:11-56 (CONTROLLER_CONFIG + AXIS_TRAVEL_RANGES)
    """
    axis: Axis
    serial: str          # Serial number for USB connection
    port: str            # COM port
    baud: int            # Baud rate
    stage: str           # Stage model number (e.g., '62309260')
    refmode: str         # Reference mode (e.g., 'FPL')
    range: TravelRange   # Physical travel limits
    default_velocity: float  # mm/s
    max_velocity: float      # mm/s


@dataclass
class AxisState:
    """Runtime state for a single axis.

    Source: hardware_controller.py:30-43 (cache variables)
    """
    axis: Axis
    position: float = 0.0
    velocity: float = 0.0
    is_connected: bool = False
    is_initialized: bool = False


@dataclass(frozen=True)
class Position:
    """3D position in mm.

    Source: main_gui.py:666-687 (waypoint usage)
    """
    x: float
    y: float
    z: float

    def __getitem__(self, axis: Axis) -> float:
        """Allow dict-like access: pos[Axis.X]"""
        return getattr(self, axis.value.lower())

    def with_axis(self, axis: Axis, value: float) -> 'Position':
        """Return new Position with one axis updated (immutability)."""
        kwargs = {'x': self.x, 'y': self.y, 'z': self.z}
        kwargs[axis.value.lower()] = value
        return Position(**kwargs)


@dataclass(frozen=True)
class Waypoint:
    """Single waypoint in automated sequence.

    Source: main_gui.py:53-56 (DEFAULT_WAYPOINTS format)
    """
    position: Position
    hold_time: float  # seconds

    @classmethod
    def from_dict(cls, data: dict) -> 'Waypoint':
        """Convert legacy dict format to Waypoint.

        Source: config.py:53-56
        Example: {'X': 10.0, 'Y': 5.0, 'Z': 20.0, 'holdTime': 1.0}
        """
        return cls(
            position=Position(
                x=data['X'],
                y=data['Y'],
                z=data['Z']
            ),
            hold_time=data['holdTime']
        )


@dataclass(frozen=True)
class SequenceConfig:
    """Configuration for automated waypoint sequence.

    Source: origintools.py:42-96 (reset function with park_pos)
    """
    waypoints: tuple[Waypoint, ...]  # Tuple for immutability
    park_when_complete: bool = True
    park_position: float = 200.0  # mm


@dataclass
class SystemState:
    """Complete system state snapshot.

    Source: main_gui.py:520-573 (connection/init state tracking)
    """
    connection: ConnectionState
    initialization: InitializationState
    is_sequence_running: bool = False


@dataclass
class ErrorDetail:
    """Error information with context.

    Published via error events from services.
    """
    origin: Axis | Literal["system"]
    message: str
    exc: Exception | None = None
