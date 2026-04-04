"""
Configuration schema validation and type definitions.

Defines the structure of defaults.json and validates all fields
are present and correctly typed.
"""

from dataclasses import dataclass
from typing import Any

from ..core.errors import ConfigurationError
from ..core.models import Axis, AxisConfig, Position, TravelRange, Waypoint


@dataclass(frozen=True)
class ConfigBundle:
    """Complete system configuration bundle.

    Encapsulates all settings from defaults.json including hardware,
    motion parameters, GUI settings, and default waypoints.

    Attributes:
        axis_configs: Per-axis hardware configuration
        reference_order: Safe initialization sequence (e.g., ['Z', 'X', 'Y'])
        park_position: Default parking position in mm
        position_update_interval: GUI polling interval in ms
        default_step_size: Manual jog step size in mm
        default_waypoints: Pre-configured waypoint sequence
    """
    axis_configs: dict[Axis, AxisConfig]
    reference_order: list[Axis]
    park_position: float
    position_update_interval: int
    default_step_size: float
    default_waypoints: list[Waypoint]


def validate_and_parse(data: dict) -> ConfigBundle:
    """Validate raw config dict and parse into typed ConfigBundle.

    Supports both new schema (all fields) and legacy schema (minimal fields).
    Legacy configs get sensible defaults for missing fields to maintain
    backwards compatibility.

    Args:
        data: Raw dict from JSON deserialization

    Returns:
        Validated and typed ConfigBundle

    Raises:
        ConfigurationError: If required fields missing or invalid types
    """
    try:
        # Parse controllers block (required)
        controllers = data['controllers']
        travel_ranges = data['travel_ranges']
        motion = data['motion']

        # Optional fields with legacy fallbacks
        gui = data.get('gui', {})
        reference_order_raw = data.get('reference_order', ['Z', 'X', 'Y'])
        default_waypoints_raw = data.get('default_waypoints', [])

        # Build axis configs
        axis_configs = {}
        for axis_name in ['X', 'Y', 'Z']:
            axis = Axis(axis_name)
            ctrl = controllers[axis_name]
            travel = travel_ranges[axis_name]

            axis_configs[axis] = AxisConfig(
                axis=axis,
                serial=ctrl['serialnum'],
                port=ctrl['port'],
                baud=ctrl['baud'],
                stage=ctrl['stage'],
                refmode=ctrl['refmode'],
                range=TravelRange(
                    min=travel['min'],
                    max=travel['max']
                ),
                default_velocity=motion['default_velocity'],
                max_velocity=motion['max_velocity']
            )

        # Parse reference order
        reference_order = [Axis(name) for name in reference_order_raw]

        # Validate reference order contains all axes exactly once (no duplicates)
        if len(reference_order) != 3 or set(reference_order) != {Axis.X, Axis.Y, Axis.Z}:
            raise ConfigurationError(
                f"reference_order must contain X, Y, Z exactly once (no duplicates), got {reference_order_raw}"
            )

        # Parse default waypoints
        default_waypoints = []
        for wp_data in default_waypoints_raw:
            pos = Position(
                x=wp_data['X'],
                y=wp_data['Y'],
                z=wp_data['Z']
            )
            hold_time = wp_data.get('holdTime', 0.0)
            default_waypoints.append(Waypoint(position=pos, hold_time=hold_time))

        return ConfigBundle(
            axis_configs=axis_configs,
            reference_order=reference_order,
            park_position=motion.get('park_position', 200.0),
            position_update_interval=gui.get('position_update_interval', 100),
            default_step_size=gui.get('default_step_size', 1.0),
            default_waypoints=default_waypoints
        )

    except (KeyError, ValueError, TypeError) as e:
        raise ConfigurationError(f"Invalid config schema: {e}")


def get_hardcoded_bundle() -> ConfigBundle:
    """Return hardcoded default configuration bundle.

    Fallback when no config files are available.
    Source: PI_Control_GUI/config.py from master branch
    """
    axis_configs = {
        Axis.X: AxisConfig(
            axis=Axis.X,
            serial='025550131',
            port='COM5',
            baud=115200,
            stage='62309260',
            refmode='FPL',
            range=TravelRange(5.0, 200.0),
            default_velocity=10.0,
            max_velocity=20.0
        ),
        Axis.Y: AxisConfig(
            axis=Axis.Y,
            serial='025550143',
            port='COM3',
            baud=115200,
            stage='62309260',
            refmode='FPL',
            range=TravelRange(0.0, 200.0),
            default_velocity=10.0,
            max_velocity=20.0
        ),
        Axis.Z: AxisConfig(
            axis=Axis.Z,
            serial='025550149',
            port='COM4',
            baud=115200,
            stage='62309260',
            refmode='FPL',
            range=TravelRange(15.0, 200.0),
            default_velocity=10.0,
            max_velocity=20.0
        ),
    }

    default_waypoints = [
        Waypoint(Position(10.0, 5.0, 20.0), 1.0),
        Waypoint(Position(25.0, 15.0, 30.0), 2.0),
    ]

    return ConfigBundle(
        axis_configs=axis_configs,
        reference_order=[Axis.Z, Axis.X, Axis.Y],
        park_position=200.0,
        position_update_interval=100,
        default_step_size=1.0,
        default_waypoints=default_waypoints
    )
