"""
Tests for configuration CLI tool.
"""

import json
import tempfile
from pathlib import Path

from PI_Control_System.config.cli import main, write_local_override


def test_write_local_override_creates_file():
    """Should create override file with provided data."""
    override_data = {
        "motion": {"park_position": 150.0}
    }

    with tempfile.TemporaryDirectory() as tmpdir:
        target = Path(tmpdir) / "local.overrides.json"

        # Temporarily patch the override path
        import PI_Control_System.config.cli as cli
        original = cli._ROOT_LOCAL_OVERRIDE
        cli._ROOT_LOCAL_OVERRIDE = target

        try:
            result_path = write_local_override(override_data)

            assert result_path == target
            assert target.exists()

            with open(target) as f:
                written = json.load(f)

            assert written == override_data

        finally:
            cli._ROOT_LOCAL_OVERRIDE = original


def test_write_local_override_merges_existing():
    """Should merge with existing override file."""
    with tempfile.TemporaryDirectory() as tmpdir:
        target = Path(tmpdir) / "local.overrides.json"

        # Write initial data
        initial = {"motion": {"park_position": 150.0}, "gui": {"default_step_size": 2.0}}
        with open(target, 'w') as f:
            json.dump(initial, f)

        # Temporarily patch the override path
        import PI_Control_System.config.cli as cli
        original = cli._ROOT_LOCAL_OVERRIDE
        cli._ROOT_LOCAL_OVERRIDE = target

        try:
            # Write new data
            new_data = {"motion": {"park_position": 175.0}}
            write_local_override(new_data)

            with open(target) as f:
                merged = json.load(f)

            # Should merge motion.park_position but preserve gui.default_step_size
            assert merged["motion"]["park_position"] == 175.0
            assert merged["gui"]["default_step_size"] == 2.0

        finally:
            cli._ROOT_LOCAL_OVERRIDE = original


def test_write_local_override_deep_merge():
    """Should deep merge nested structures without losing fields.

    Critical: When updating X.port, should preserve X.baud and other X fields.
    """
    with tempfile.TemporaryDirectory() as tmpdir:
        target = Path(tmpdir) / "local.overrides.json"

        # Initial state: X axis with custom baud rate
        initial = {
            "controllers": {
                "X": {
                    "port": "COM5",
                    "baud": 9600  # Custom baud rate
                }
            }
        }
        with open(target, 'w') as f:
            json.dump(initial, f)

        import PI_Control_System.config.cli as cli
        original = cli._ROOT_LOCAL_OVERRIDE
        cli._ROOT_LOCAL_OVERRIDE = target

        try:
            # Update just the port (simulates set-port command)
            new_data = {
                "controllers": {
                    "X": {
                        "port": "COM7"
                    }
                }
            }
            write_local_override(new_data)

            with open(target) as f:
                merged = json.load(f)

            # Should have new port AND preserved baud
            assert merged["controllers"]["X"]["port"] == "COM7"
            assert merged["controllers"]["X"]["baud"] == 9600

        finally:
            cli._ROOT_LOCAL_OVERRIDE = original


def test_cli_show_command():
    """Should display current configuration without error."""
    result = main(['show'])
    assert result == 0


def test_cli_set_port():
    """Should update axis port in override file."""
    with tempfile.TemporaryDirectory() as tmpdir:
        target = Path(tmpdir) / "local.overrides.json"

        import PI_Control_System.config.cli as cli
        original = cli._ROOT_LOCAL_OVERRIDE
        cli._ROOT_LOCAL_OVERRIDE = target

        try:
            result = main(['set-port', 'X', 'COM9'])
            assert result == 0
            assert target.exists()

            with open(target) as f:
                data = json.load(f)

            assert data["controllers"]["X"]["port"] == "COM9"

        finally:
            cli._ROOT_LOCAL_OVERRIDE = original


def test_cli_set_park_position():
    """Should update park position in override file."""
    with tempfile.TemporaryDirectory() as tmpdir:
        target = Path(tmpdir) / "local.overrides.json"

        import PI_Control_System.config.cli as cli
        original = cli._ROOT_LOCAL_OVERRIDE
        cli._ROOT_LOCAL_OVERRIDE = target

        try:
            result = main(['set-park-position', '185.5'])
            assert result == 0
            assert target.exists()

            with open(target) as f:
                data = json.load(f)

            assert data["motion"]["park_position"] == 185.5

        finally:
            cli._ROOT_LOCAL_OVERRIDE = original


def test_cli_clear_with_force():
    """Should delete override file when --force specified."""
    with tempfile.TemporaryDirectory() as tmpdir:
        target = Path(tmpdir) / "local.overrides.json"

        # Create existing file
        with open(target, 'w') as f:
            json.dump({"motion": {"park_position": 150.0}}, f)

        import PI_Control_System.config.cli as cli
        original = cli._ROOT_LOCAL_OVERRIDE
        cli._ROOT_LOCAL_OVERRIDE = target

        try:
            result = main(['clear', '--force'])
            assert result == 0
            assert not target.exists()

        finally:
            cli._ROOT_LOCAL_OVERRIDE = original


def test_cli_invalid_axis():
    """Should reject invalid axis names."""
    import sys
    with tempfile.TemporaryDirectory() as tmpdir:
        target = Path(tmpdir) / "local.overrides.json"

        import PI_Control_System.config.cli as cli
        original = cli._ROOT_LOCAL_OVERRIDE
        cli._ROOT_LOCAL_OVERRIDE = target

        try:
            # Argparse calls sys.exit() on invalid input
            try:
                result = main(['set-port', 'W', 'COM5'])
                assert False, "Should have raised SystemExit"
            except SystemExit as e:
                assert e.code != 0  # Non-zero exit code

        finally:
            cli._ROOT_LOCAL_OVERRIDE = original


if __name__ == '__main__':
    test_write_local_override_creates_file()
    test_write_local_override_merges_existing()
    test_write_local_override_deep_merge()
    test_cli_show_command()
    test_cli_set_port()
    test_cli_set_park_position()
    test_cli_clear_with_force()
    test_cli_invalid_axis()

    print("✓ All CLI tests passed")
