import sys
from pathlib import Path

# Add device_drivers/ to sys.path so "from PI_Control_System.*" imports work
_dd_dir = str(Path(__file__).resolve().parent.parent.parent)
if _dd_dir not in sys.path:
    sys.path.insert(0, _dd_dir)
