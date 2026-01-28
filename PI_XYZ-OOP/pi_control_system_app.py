#!/usr/bin/env python
"""
PI Stage Control System - New OOP Architecture

Entry point for the refactored PI control system.
Supports dual-launch mode with --legacy flag for backwards compatibility.

Usage:
    python pi_control_system_app.py              # Launch new OOP GUI
    python pi_control_system_app.py --mock       # Launch with mock hardware
    python pi_control_system_app.py --legacy     # Launch legacy GUI
"""

import sys
import argparse
from pathlib import Path

# Ensure project root is in path
PROJECT_ROOT = Path(__file__).parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


def launch_legacy():
    """Launch legacy GUI."""
    print("Launching legacy PI Control GUI...")
    legacy_path = PROJECT_ROOT / "legacy" / "PI_Control_GUI"
    sys.path.insert(0, str(legacy_path))

    try:
        from main_gui import PIStageGUI
        from PySide6.QtWidgets import QApplication

        app = QApplication(sys.argv)
        gui = PIStageGUI()
        gui.show()
        sys.exit(app.exec())
    except ImportError as e:
        print(f"Error: Could not import legacy GUI: {e}")
        print(f"Expected path: {legacy_path}")
        sys.exit(1)


def launch_new(use_mock: bool = False):
    """Launch new OOP architecture GUI."""
    mode = "mock hardware" if use_mock else "real hardware"
    print(f"Launching new PI Control System ({mode})...")

    try:
        from PI_Control_System.app_factory import run_app
        sys.exit(run_app(use_mock=use_mock))
    except ImportError as e:
        print(f"Error: Could not import new GUI: {e}")
        sys.exit(1)


def main():
    """Parse arguments and launch appropriate GUI."""
    parser = argparse.ArgumentParser(
        description="PI Stage Control System",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s                 Launch new OOP GUI with real hardware
  %(prog)s --mock          Launch new OOP GUI with mock hardware (testing)
  %(prog)s --legacy        Launch legacy GUI
        """
    )

    parser.add_argument(
        '--legacy',
        action='store_true',
        help='Launch legacy GUI instead of new OOP architecture'
    )

    parser.add_argument(
        '--mock',
        action='store_true',
        help='Use mock hardware controllers (for testing without physical hardware)'
    )

    args = parser.parse_args()

    if args.legacy:
        if args.mock:
            print("Warning: --mock flag ignored when using --legacy")
        launch_legacy()
    else:
        launch_new(use_mock=args.mock)


if __name__ == '__main__':
    main()
