"""
PI Control System - OOP Refactor

Clean architecture implementation for 3-axis PI stage control.
"""

import os
import sys
from pathlib import Path

__version__ = "2.0.0-dev"

# ============================================================
# PI DLL Setup - MUST happen before any pipython imports
# ============================================================
def _setup_pi_dll_path():
    """Add PI DLL directories to system PATH.

    This ensures pipython can find PI_GCS2_DLL_x64.dll.
    Must be called before importing pipython.
    """
    # Get the project root (CTA folder)
    project_root = Path(__file__).parent.parent.parent

    # Possible DLL locations (in order of preference)
    dll_dirs = [
        project_root,  # CTA/
        project_root / "device_drivers",  # CTA/device_drivers/
        Path(r"C:\Program Files\PI\PI_GCS2"),  # Standard PI install
        Path(r"C:\Program Files (x86)\PI\PI_GCS2"),
    ]

    # Get current PATH
    current_path = os.environ.get('PATH', '')

    # Add existing DLL directories to PATH
    for dll_dir in dll_dirs:
        if dll_dir.exists():
            dll_dir_str = str(dll_dir)
            if dll_dir_str not in current_path:
                os.environ['PATH'] = dll_dir_str + os.pathsep + current_path
                current_path = os.environ['PATH']

                # Check if the DLL exists in this directory
                dll_file = dll_dir / "PI_GCS2_DLL_x64.dll"
                if dll_file.exists():
                    print(f"[PI] Found DLL at: {dll_file}")

# Run setup immediately when this module is imported
_setup_pi_dll_path()
