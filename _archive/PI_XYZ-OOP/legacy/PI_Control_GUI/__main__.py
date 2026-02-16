#!/usr/bin/python
# -*- coding: utf-8 -*-
"""Module entry point: python -m PI_Control_GUI"""

import sys
from PySide6.QtWidgets import QApplication
from .main_gui import PIStageGUI


def main() -> int:
    app = QApplication(sys.argv)
    window = PIStageGUI()
    window.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())

