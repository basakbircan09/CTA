import sys
import os
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent

# DLL paths — must be set before importing PI libraries
PI_DLL_DIR = PROJECT_ROOT / "lib" / "pi_dlls"
if PI_DLL_DIR.exists():
    os.add_dll_directory(str(PI_DLL_DIR))
    os.environ["PATH"] = str(PI_DLL_DIR) + os.pathsep + os.environ.get("PATH", "")

if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from PySide6.QtWidgets import QApplication
from gui.app_window import SimpleStageApp


def main():
    app = QApplication(sys.argv)
    window = SimpleStageApp(use_mock=False)
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
