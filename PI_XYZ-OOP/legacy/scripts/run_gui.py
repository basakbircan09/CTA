#!/usr/bin/env python
# Simple launcher for the PI Control GUI

import sys
from PySide6.QtWidgets import QApplication
from PI_Control_GUI.main_gui import PIStageGUI


def main() -> int:
    app = QApplication(sys.argv)
    window = PIStageGUI()
    window.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())

