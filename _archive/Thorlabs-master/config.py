"""
Application-wide configuration for the Thorlabs camera controller.

This module centralizes constants, filesystem locations, and default
operational parameters used across the codebase. Importing this module
performs lightweight directory setup so dependent components can assume
the presence of preset and snapshot folders.
"""

from __future__ import annotations

from pathlib import Path

APP_NAME = "Thorlabs Camera Control"
APP_VERSION = "1.0.0"

PROJECT_ROOT = Path(__file__).parent
THORCAM_DLL_PATH = PROJECT_ROOT / "ThorCam"
PRESETS_DIR = PROJECT_ROOT / "presets"
SNAPSHOTS_DIR = PROJECT_ROOT / "snapshots"

DEFAULT_EXPOSURE_MS = 30.0
DEFAULT_GAIN_DB = 0.0
DEFAULT_WHITE_BALANCE = (1.0, 1.0, 1.0)
DEFAULT_ROI = None  # When None, camera uses full sensor area

TARGET_FPS = 30
DISPLAY_SCALE = 0.5

for _path in (PRESETS_DIR, SNAPSHOTS_DIR):
    _path.mkdir(exist_ok=True)

