"""
Configuration loader with merge chain.

Merge order (later overrides earlier):
1. Package defaults (config/defaults.json)
2. Package-level override (config/local.overrides.json)
3. Project root override (local.overrides.json)
4. PI_STAGE_CONFIG_PATH environment variable
5. Explicit path parameter

Each layer is deep-merged with the previous, allowing selective overrides
of individual fields without requiring a complete config file.
"""

import json
import os
from pathlib import Path
from typing import Optional, Any

from ..core.errors import ConfigurationError
from .schema import ConfigBundle, validate_and_parse, get_hardcoded_bundle

_CONFIG_DIR = Path(__file__).parent
_PACKAGE_DEFAULT_FILE = _CONFIG_DIR / "defaults.json"
_PACKAGE_LOCAL_OVERRIDE = _CONFIG_DIR / "local.overrides.json"
_ROOT_LOCAL_OVERRIDE = Path("local.overrides.json")
_LEGACY_DEFAULT_FILE = Path("defaults.json")


def load_config(base_path: Optional[Path] = None) -> ConfigBundle:
    """Load system configuration with merge chain.

    Builds configuration by deep-merging layers in order:
    1. Package defaults (if exists) OR legacy root defaults OR hardcoded fallback
    2. Package-level local.overrides.json (if exists)
    3. Root-level local.overrides.json (if exists)
    4. PI_STAGE_CONFIG_PATH file (if set and exists)
    5. Explicit base_path (if provided and exists)

    Each layer selectively overrides fields from previous layers.
    If no files exist at all, returns hardcoded defaults.

    Args:
        base_path: Optional explicit path to override file

    Returns:
        ConfigBundle containing merged settings

    Raises:
        ConfigurationError: If any config file is malformed

    Source: INTERFACES.md merge order specification
    """
    # Collect all layers in merge order
    layers = []

    # Layer 1: Base defaults (package > legacy root > hardcoded)
    if _PACKAGE_DEFAULT_FILE.exists():
        layers.append(_load_json(_PACKAGE_DEFAULT_FILE))
    elif _LEGACY_DEFAULT_FILE.exists():
        # Legacy repo-root defaults.json for backwards compatibility
        layers.append(_load_json(_LEGACY_DEFAULT_FILE))
    else:
        # Use hardcoded as base layer (convert bundle to dict for merging)
        hardcoded = get_hardcoded_bundle()
        layers.append(_bundle_to_dict(hardcoded))

    # Layer 2: Package-level override
    if _PACKAGE_LOCAL_OVERRIDE.exists():
        layers.append(_load_json(_PACKAGE_LOCAL_OVERRIDE))

    # Layer 3: Root-level override
    if _ROOT_LOCAL_OVERRIDE.exists():
        layers.append(_load_json(_ROOT_LOCAL_OVERRIDE))

    # Layer 4: Environment variable
    env_path = os.getenv("PI_STAGE_CONFIG_PATH")
    if env_path:
        path = Path(env_path)
        if path.exists():
            layers.append(_load_json(path))

    # Layer 5: Explicit path
    if base_path and base_path.exists():
        layers.append(_load_json(base_path))

    # Merge all layers
    merged = layers[0]
    for layer in layers[1:]:
        merged = _deep_merge(merged, layer)

    # Validate and parse final merged config
    return validate_and_parse(merged)


def _load_json(path: Path) -> dict:
    """Load raw JSON dict from file.

    Args:
        path: Path to JSON file

    Returns:
        Raw dict (not yet validated)

    Raises:
        ConfigurationError: If file cannot be read or parsed
    """
    try:
        with open(path, 'r') as f:
            return json.load(f)
    except (json.JSONDecodeError, IOError) as e:
        raise ConfigurationError(f"Failed to load config from {path}: {e}")


def _bundle_to_dict(bundle: ConfigBundle) -> dict[str, Any]:
    """Convert ConfigBundle back to dict format for merging.

    Args:
        bundle: ConfigBundle to convert

    Returns:
        Dict matching JSON schema structure
    """
    from ..core.models import Axis

    # Rebuild controllers block
    controllers = {}
    for axis in [Axis.X, Axis.Y, Axis.Z]:
        cfg = bundle.axis_configs[axis]
        controllers[axis.value] = {
            "port": cfg.port,
            "baud": cfg.baud,
            "stage": cfg.stage,
            "refmode": cfg.refmode,
            "serialnum": cfg.serial
        }

    # Rebuild travel_ranges block
    travel_ranges = {}
    for axis in [Axis.X, Axis.Y, Axis.Z]:
        cfg = bundle.axis_configs[axis]
        travel_ranges[axis.value] = {
            "min": cfg.range.min,
            "max": cfg.range.max
        }

    # Rebuild motion block (using first axis for velocities - they're identical)
    first_cfg = bundle.axis_configs[Axis.X]
    motion = {
        "default_velocity": first_cfg.default_velocity,
        "max_velocity": first_cfg.max_velocity,
        "park_position": bundle.park_position
    }

    # Rebuild gui block
    gui = {
        "position_update_interval": bundle.position_update_interval,
        "default_step_size": bundle.default_step_size
    }

    # Rebuild default_waypoints
    default_waypoints = []
    for wp in bundle.default_waypoints:
        default_waypoints.append({
            "X": wp.position.x,
            "Y": wp.position.y,
            "Z": wp.position.z,
            "holdTime": wp.hold_time
        })

    return {
        "controllers": controllers,
        "reference_order": [axis.value for axis in bundle.reference_order],
        "travel_ranges": travel_ranges,
        "motion": motion,
        "gui": gui,
        "default_waypoints": default_waypoints
    }


def _deep_merge(base: dict[str, Any], override: dict[str, Any]) -> dict[str, Any]:
    """Deep merge override dict into base dict.

    For nested dicts, merges recursively. For other types, override replaces base.
    Neither input dict is mutated.

    Args:
        base: Base configuration
        override: Override values

    Returns:
        New dict with merged values

    Example:
        >>> base = {"motion": {"velocity": 10, "accel": 5}, "gui": {"theme": "dark"}}
        >>> override = {"motion": {"velocity": 15}}
        >>> _deep_merge(base, override)
        {"motion": {"velocity": 15, "accel": 5}, "gui": {"theme": "dark"}}
    """
    result = base.copy()

    for key, value in override.items():
        if key in result and isinstance(result[key], dict) and isinstance(value, dict):
            # Recursively merge nested dicts
            result[key] = _deep_merge(result[key], value)
        else:
            # Replace value
            result[key] = value

    return result


