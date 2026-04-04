"""
Unit tests for configuration loader.
"""

import json
import tempfile
from pathlib import Path

from PI_Control_System.core.models import Axis
from PI_Control_System.config.loader import load_config
from PI_Control_System.core.errors import ConfigurationError


def test_hardcoded_defaults():
    """Should load hardcoded defaults when no files present."""
    # Use explicit non-existent path to bypass defaults.json
    bundle = load_config(Path("/nonexistent/fake/path.json"))

    assert Axis.X in bundle.axis_configs
    assert Axis.Y in bundle.axis_configs
    assert Axis.Z in bundle.axis_configs

    # Verify master branch values
    assert bundle.axis_configs[Axis.X].serial == '025550131'
    assert bundle.axis_configs[Axis.X].port == 'COM5'
    assert bundle.axis_configs[Axis.X].range.min == 5.0
    assert bundle.axis_configs[Axis.X].range.max == 200.0

    # Verify reference order
    assert bundle.reference_order == [Axis.Z, Axis.X, Axis.Y]

    # Verify GUI/motion params
    assert bundle.park_position == 200.0
    assert bundle.position_update_interval == 100
    assert bundle.default_step_size == 1.0

    # Verify default waypoints
    assert len(bundle.default_waypoints) == 2
    assert bundle.default_waypoints[0].position.x == 10.0


def test_load_from_json():
    """Should load from JSON file."""
    test_config = {
        "controllers": {
            "X": {
                "port": "COM10",
                "baud": 115200,
                "stage": "62309260",
                "refmode": "FPL",
                "serialnum": "999999999"
            },
            "Y": {
                "port": "COM3",
                "baud": 115200,
                "stage": "62309260",
                "refmode": "FPL",
                "serialnum": "025550143"
            },
            "Z": {
                "port": "COM4",
                "baud": 115200,
                "stage": "62309260",
                "refmode": "FPL",
                "serialnum": "025550149"
            }
        },
        "reference_order": ["Z", "X", "Y"],
        "travel_ranges": {
            "X": {"min": 5.0, "max": 200.0},
            "Y": {"min": 0.0, "max": 200.0},
            "Z": {"min": 15.0, "max": 200.0}
        },
        "motion": {
            "default_velocity": 10.0,
            "max_velocity": 20.0,
            "park_position": 200.0
        },
        "gui": {
            "position_update_interval": 100,
            "default_step_size": 1.0
        },
        "default_waypoints": [
            {"X": 50.0, "Y": 60.0, "Z": 70.0, "holdTime": 3.0}
        ]
    }

    with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
        json.dump(test_config, f)
        temp_path = Path(f.name)

    try:
        bundle = load_config(temp_path)

        assert bundle.axis_configs[Axis.X].serial == "999999999"
        assert bundle.axis_configs[Axis.X].port == "COM10"

        # Verify all fields are loaded
        assert len(bundle.default_waypoints) == 1
        assert bundle.default_waypoints[0].position.x == 50.0
        assert bundle.default_waypoints[0].hold_time == 3.0

    finally:
        temp_path.unlink()


def test_invalid_json():
    """Should raise ConfigurationError on invalid JSON."""
    with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
        f.write("{invalid json")
        temp_path = Path(f.name)

    try:
        try:
            load_config(temp_path)
            assert False, "Should have raised ConfigurationError"
        except ConfigurationError as e:
            assert "Failed to load config" in str(e)
    finally:
        temp_path.unlink()


def test_schema_validation_missing_controllers():
    """Should raise ConfigurationError if controllers block missing from merged config."""
    from PI_Control_System.config import schema

    # Directly test schema validation (bypass loader merge)
    test_config = {
        "travel_ranges": {
            "X": {"min": 5.0, "max": 200.0},
            "Y": {"min": 0.0, "max": 200.0},
            "Z": {"min": 15.0, "max": 200.0}
        },
        "motion": {"default_velocity": 10.0, "max_velocity": 20.0, "park_position": 200.0}
    }

    try:
        schema.validate_and_parse(test_config)
        assert False, "Should have raised ConfigurationError"
    except ConfigurationError as e:
        assert "Invalid config schema" in str(e)


def test_schema_validation_invalid_reference_order():
    """Should raise ConfigurationError if reference_order invalid."""
    test_config = {
        "controllers": {
            "X": {"port": "COM5", "baud": 115200, "stage": "62309260", "refmode": "FPL", "serialnum": "025550131"},
            "Y": {"port": "COM3", "baud": 115200, "stage": "62309260", "refmode": "FPL", "serialnum": "025550143"},
            "Z": {"port": "COM4", "baud": 115200, "stage": "62309260", "refmode": "FPL", "serialnum": "025550149"}
        },
        "reference_order": ["Z", "X"],  # Missing Y
        "travel_ranges": {
            "X": {"min": 5.0, "max": 200.0},
            "Y": {"min": 0.0, "max": 200.0},
            "Z": {"min": 15.0, "max": 200.0}
        },
        "motion": {"default_velocity": 10.0, "max_velocity": 20.0, "park_position": 200.0},
        "gui": {"position_update_interval": 100, "default_step_size": 1.0},
        "default_waypoints": []
    }

    with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
        json.dump(test_config, f)
        temp_path = Path(f.name)

    try:
        try:
            load_config(temp_path)
            assert False, "Should have raised ConfigurationError"
        except ConfigurationError as e:
            assert "reference_order must contain X, Y, Z exactly once" in str(e)
    finally:
        temp_path.unlink()


def test_schema_validation_duplicate_reference_order():
    """Should raise ConfigurationError if reference_order has duplicates."""
    test_config = {
        "controllers": {
            "X": {"port": "COM5", "baud": 115200, "stage": "62309260", "refmode": "FPL", "serialnum": "025550131"},
            "Y": {"port": "COM3", "baud": 115200, "stage": "62309260", "refmode": "FPL", "serialnum": "025550143"},
            "Z": {"port": "COM4", "baud": 115200, "stage": "62309260", "refmode": "FPL", "serialnum": "025550149"}
        },
        "reference_order": ["Z", "X", "Y", "Z"],  # Duplicate Z
        "travel_ranges": {
            "X": {"min": 5.0, "max": 200.0},
            "Y": {"min": 0.0, "max": 200.0},
            "Z": {"min": 15.0, "max": 200.0}
        },
        "motion": {"default_velocity": 10.0, "max_velocity": 20.0, "park_position": 200.0},
        "gui": {"position_update_interval": 100, "default_step_size": 1.0},
        "default_waypoints": []
    }

    with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
        json.dump(test_config, f)
        temp_path = Path(f.name)

    try:
        try:
            load_config(temp_path)
            assert False, "Should have raised ConfigurationError"
        except ConfigurationError as e:
            assert "no duplicates" in str(e)
    finally:
        temp_path.unlink()


def test_legacy_schema_compatibility():
    """Should load legacy config with minimal fields (backwards compatibility).

    With merge strategy, missing fields are filled from defaults.json,
    so default_waypoints will include the demo waypoints from defaults.
    """
    legacy_config = {
        "controllers": {
            "X": {"port": "COM5", "baud": 115200, "stage": "62309260", "refmode": "FPL", "serialnum": "025550131"},
            "Y": {"port": "COM3", "baud": 115200, "stage": "62309260", "refmode": "FPL", "serialnum": "025550143"},
            "Z": {"port": "COM4", "baud": 115200, "stage": "62309260", "refmode": "FPL", "serialnum": "025550149"}
        },
        "travel_ranges": {
            "X": {"min": 5.0, "max": 200.0},
            "Y": {"min": 0.0, "max": 200.0},
            "Z": {"min": 15.0, "max": 200.0}
        },
        "motion": {
            "default_velocity": 10.0,
            "max_velocity": 20.0
            # park_position missing - merged from defaults
        }
        # gui, reference_order, default_waypoints all merged from defaults.json
    }

    with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
        json.dump(legacy_config, f)
        temp_path = Path(f.name)

    try:
        bundle = load_config(temp_path)

        # Verify hardware config loads
        assert bundle.axis_configs[Axis.X].serial == "025550131"

        # Verify defaults merged from defaults.json
        assert bundle.reference_order == [Axis.Z, Axis.X, Axis.Y]
        assert bundle.park_position == 200.0
        assert bundle.position_update_interval == 100
        assert bundle.default_step_size == 1.0
        # Waypoints merged from defaults.json (not empty)
        assert len(bundle.default_waypoints) == 2

    finally:
        temp_path.unlink()


def test_merge_precedence():
    """Should merge configs with correct precedence: defaults < local < env < explicit."""
    import os

    # Create temporary override files
    root_override = {"motion": {"park_position": 150.0}, "gui": {"default_step_size": 2.5}}
    env_override = {"motion": {"park_position": 175.0}}
    explicit_override = {"motion": {"park_position": 190.0}}

    with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f_root:
        json.dump(root_override, f_root)
        root_path = Path(f_root.name)

    with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f_env:
        json.dump(env_override, f_env)
        env_path = Path(f_env.name)

    with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f_explicit:
        json.dump(explicit_override, f_explicit)
        explicit_path = Path(f_explicit.name)

    import PI_Control_System.config.loader as loader
    original_root = loader._ROOT_LOCAL_OVERRIDE
    loader._ROOT_LOCAL_OVERRIDE = root_path

    original_env = os.environ.get("PI_STAGE_CONFIG_PATH")

    try:
        # Test 1: Root override takes precedence over defaults
        bundle = load_config()
        assert bundle.park_position == 150.0  # From root override
        assert bundle.default_step_size == 2.5  # From root override

        # Test 2: Env override takes precedence over root
        os.environ["PI_STAGE_CONFIG_PATH"] = str(env_path)
        bundle = load_config()
        assert bundle.park_position == 175.0  # From env override
        assert bundle.default_step_size == 2.5  # Still from root (not overridden by env)

        # Test 3: Explicit path takes precedence over all
        bundle = load_config(explicit_path)
        assert bundle.park_position == 190.0  # From explicit path
        assert bundle.default_step_size == 2.5  # Still from root

    finally:
        root_path.unlink()
        env_path.unlink()
        explicit_path.unlink()
        loader._ROOT_LOCAL_OVERRIDE = original_root
        if original_env:
            os.environ["PI_STAGE_CONFIG_PATH"] = original_env
        elif "PI_STAGE_CONFIG_PATH" in os.environ:
            del os.environ["PI_STAGE_CONFIG_PATH"]


def test_override_only_without_defaults():
    """Should support override-only config when defaults.json missing.

    Critical for site-specific deployments where technician provides
    complete config via PI_STAGE_CONFIG_PATH without needing defaults.json.
    """
    import os

    # Complete site config
    site_config = {
        "controllers": {
            "X": {"port": "COM10", "baud": 115200, "stage": "62309260", "refmode": "FPL", "serialnum": "999999999"},
            "Y": {"port": "COM11", "baud": 115200, "stage": "62309260", "refmode": "FPL", "serialnum": "888888888"},
            "Z": {"port": "COM12", "baud": 115200, "stage": "62309260", "refmode": "FPL", "serialnum": "777777777"}
        },
        "reference_order": ["Z", "X", "Y"],
        "travel_ranges": {
            "X": {"min": 0.0, "max": 150.0},
            "Y": {"min": 0.0, "max": 150.0},
            "Z": {"min": 10.0, "max": 150.0}
        },
        "motion": {
            "default_velocity": 15.0,
            "max_velocity": 25.0,
            "park_position": 150.0
        },
        "gui": {
            "position_update_interval": 50,
            "default_step_size": 0.5
        },
        "default_waypoints": []
    }

    with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
        json.dump(site_config, f)
        site_path = Path(f.name)

    import PI_Control_System.config.loader as loader
    original_default = loader._PACKAGE_DEFAULT_FILE
    original_env = os.environ.get("PI_STAGE_CONFIG_PATH")

    # Simulate missing defaults.json
    loader._PACKAGE_DEFAULT_FILE = Path("/nonexistent/defaults.json")
    os.environ["PI_STAGE_CONFIG_PATH"] = str(site_path)

    try:
        bundle = load_config()

        # Verify site config was loaded (not hardcoded defaults)
        assert bundle.axis_configs[Axis.X].serial == "999999999"
        assert bundle.axis_configs[Axis.X].port == "COM10"
        assert bundle.park_position == 150.0
        assert bundle.position_update_interval == 50

    finally:
        site_path.unlink()
        loader._PACKAGE_DEFAULT_FILE = original_default
        if original_env:
            os.environ["PI_STAGE_CONFIG_PATH"] = original_env
        elif "PI_STAGE_CONFIG_PATH" in os.environ:
            del os.environ["PI_STAGE_CONFIG_PATH"]


def test_legacy_root_defaults_fallback():
    """Should load legacy repo-root defaults.json when package defaults missing.

    Preserves backwards compatibility for repos with defaults.json at root
    when PI_Control_System/config/defaults.json doesn't exist.
    """
    import PI_Control_System.config.loader as loader
    original_package = loader._PACKAGE_DEFAULT_FILE
    original_legacy = loader._LEGACY_DEFAULT_FILE

    # Create legacy root defaults.json
    legacy_data = {
        "controllers": {
            "X": {"port": "COM8", "baud": 115200, "stage": "62309260", "refmode": "FPL", "serialnum": "111111111"},
            "Y": {"port": "COM9", "baud": 115200, "stage": "62309260", "refmode": "FPL", "serialnum": "222222222"},
            "Z": {"port": "COM10", "baud": 115200, "stage": "62309260", "refmode": "FPL", "serialnum": "333333333"}
        },
        "reference_order": ["Z", "X", "Y"],
        "travel_ranges": {
            "X": {"min": 5.0, "max": 200.0},
            "Y": {"min": 0.0, "max": 200.0},
            "Z": {"min": 15.0, "max": 200.0}
        },
        "motion": {
            "default_velocity": 10.0,
            "max_velocity": 20.0,
            "park_position": 200.0
        },
        "gui": {
            "position_update_interval": 100,
            "default_step_size": 1.0
        },
        "default_waypoints": []
    }

    with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
        json.dump(legacy_data, f)
        legacy_path = Path(f.name)

    # Simulate package defaults missing, legacy at root exists
    loader._PACKAGE_DEFAULT_FILE = Path("/nonexistent/package/defaults.json")
    loader._LEGACY_DEFAULT_FILE = legacy_path

    try:
        bundle = load_config()

        # Should load from legacy root defaults
        assert bundle.axis_configs[Axis.X].serial == "111111111"
        assert bundle.axis_configs[Axis.X].port == "COM8"
        assert bundle.axis_configs[Axis.Y].port == "COM9"

    finally:
        legacy_path.unlink()
        loader._PACKAGE_DEFAULT_FILE = original_package
        loader._LEGACY_DEFAULT_FILE = original_legacy


if __name__ == '__main__':
    test_hardcoded_defaults()
    test_load_from_json()
    test_invalid_json()
    test_schema_validation_missing_controllers()
    test_schema_validation_invalid_reference_order()
    test_schema_validation_duplicate_reference_order()
    test_legacy_schema_compatibility()
    test_merge_precedence()
    test_override_only_without_defaults()
    test_legacy_root_defaults_fallback()

    print("✓ All config tests passed")
