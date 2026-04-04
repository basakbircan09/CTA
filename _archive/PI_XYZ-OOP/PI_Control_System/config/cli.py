"""
Configuration CLI tool for provisioning local overrides.

Provides commands to generate and manage local.overrides.json files
for machine-specific configuration without modifying defaults.
"""

import argparse
import json
import sys
from pathlib import Path
from typing import Optional

from ..core.models import Axis
from .loader import _ROOT_LOCAL_OVERRIDE, _PACKAGE_LOCAL_OVERRIDE, load_config


def write_local_override(data: dict, package_level: bool = False) -> Path:
    """Write local override file with merge-safe handling.

    Args:
        data: Override data (partial config dict)
        package_level: If True, writes to package config dir; else project root

    Returns:
        Path to written override file

    Raises:
        IOError: If file cannot be written
    """
    from .loader import _deep_merge

    target_path = _PACKAGE_LOCAL_OVERRIDE if package_level else _ROOT_LOCAL_OVERRIDE

    # If file exists, deep merge with existing content
    if target_path.exists():
        with open(target_path, 'r') as f:
            existing = json.load(f)

        # Deep merge to preserve nested fields
        data = _deep_merge(existing, data)

    # Write with pretty formatting
    with open(target_path, 'w') as f:
        json.dump(data, f, indent=2)

    return target_path


def cmd_show_config(args: argparse.Namespace) -> int:
    """Show current merged configuration."""
    try:
        bundle = load_config()

        print("Current Configuration:")
        print(f"\nReference Order: {[a.value for a in bundle.reference_order]}")
        print(f"Park Position: {bundle.park_position} mm")
        print(f"Position Update Interval: {bundle.position_update_interval} ms")
        print(f"Default Step Size: {bundle.default_step_size} mm")
        print(f"Default Waypoints: {len(bundle.default_waypoints)}")

        print("\nAxis Configurations:")
        for axis in [Axis.X, Axis.Y, Axis.Z]:
            cfg = bundle.axis_configs[axis]
            print(f"  {axis.value}: {cfg.port} (serial: {cfg.serial})")

        return 0

    except Exception as e:
        print(f"Error loading config: {e}", file=sys.stderr)
        return 1


def cmd_set_port(args: argparse.Namespace) -> int:
    """Set COM port for an axis."""
    axis = args.axis.upper()
    if axis not in ['X', 'Y', 'Z']:
        print(f"Error: Invalid axis '{axis}'. Must be X, Y, or Z.", file=sys.stderr)
        return 1

    override = {
        "controllers": {
            axis: {"port": args.port}
        }
    }

    try:
        path = write_local_override(override, package_level=args.package)
        print(f"Updated {axis} port to {args.port}")
        print(f"Override written to: {path.absolute()}")
        return 0

    except Exception as e:
        print(f"Error writing override: {e}", file=sys.stderr)
        return 1


def cmd_set_park_position(args: argparse.Namespace) -> int:
    """Set park position."""
    override = {
        "motion": {
            "park_position": args.position
        }
    }

    try:
        path = write_local_override(override, package_level=args.package)
        print(f"Updated park position to {args.position} mm")
        print(f"Override written to: {path.absolute()}")
        return 0

    except Exception as e:
        print(f"Error writing override: {e}", file=sys.stderr)
        return 1


def cmd_clear_overrides(args: argparse.Namespace) -> int:
    """Clear local override file."""
    target_path = _PACKAGE_LOCAL_OVERRIDE if args.package else _ROOT_LOCAL_OVERRIDE

    if not target_path.exists():
        print(f"No override file at {target_path.absolute()}")
        return 0

    if not args.force:
        response = input(f"Delete {target_path.absolute()}? [y/N]: ")
        if response.lower() != 'y':
            print("Cancelled")
            return 0

    try:
        target_path.unlink()
        print(f"Deleted {target_path.absolute()}")
        return 0

    except Exception as e:
        print(f"Error deleting override: {e}", file=sys.stderr)
        return 1


def main(argv: Optional[list[str]] = None) -> int:
    """CLI entry point."""
    parser = argparse.ArgumentParser(
        description="PI Stage Configuration Tool",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Show current merged configuration
  python -m PI_Control_System.config.cli show

  # Set X axis COM port in project root override
  python -m PI_Control_System.config.cli set-port X COM7

  # Set park position in package-level override
  python -m PI_Control_System.config.cli set-park-position 180.0 --package

  # Clear project root overrides
  python -m PI_Control_System.config.cli clear --force
        """
    )

    subparsers = parser.add_subparsers(dest='command', required=True)

    # Show command
    show_parser = subparsers.add_parser('show', help='Show current configuration')
    show_parser.set_defaults(func=cmd_show_config)

    # Set-port command
    port_parser = subparsers.add_parser('set-port', help='Set COM port for an axis')
    port_parser.add_argument('axis', choices=['X', 'Y', 'Z', 'x', 'y', 'z'], help='Axis name')
    port_parser.add_argument('port', help='COM port (e.g., COM5)')
    port_parser.add_argument('--package', action='store_true',
                            help='Write to package-level override (default: project root)')
    port_parser.set_defaults(func=cmd_set_port)

    # Set-park-position command
    park_parser = subparsers.add_parser('set-park-position', help='Set park position')
    park_parser.add_argument('position', type=float, help='Park position in mm')
    park_parser.add_argument('--package', action='store_true',
                            help='Write to package-level override (default: project root)')
    park_parser.set_defaults(func=cmd_set_park_position)

    # Clear command
    clear_parser = subparsers.add_parser('clear', help='Clear local overrides')
    clear_parser.add_argument('--package', action='store_true',
                             help='Clear package-level override (default: project root)')
    clear_parser.add_argument('--force', action='store_true',
                             help='Skip confirmation prompt')
    clear_parser.set_defaults(func=cmd_clear_overrides)

    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == '__main__':
    sys.exit(main())
