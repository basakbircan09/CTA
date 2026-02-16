"""
Qt application entry point.
"""

from __future__ import annotations

import logging
import sys
from datetime import datetime

from PySide6.QtWidgets import QApplication

import config
from app.controller import ApplicationController


def setup_logging() -> None:
    """Configure application logging."""
    log_dir = config.PROJECT_ROOT / "logs"
    log_dir.mkdir(exist_ok=True)

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    log_file = log_dir / f"app_{timestamp}.log"

    # Clear existing handlers to support multiple invocations
    root_logger = logging.getLogger()
    if root_logger.hasHandlers():
        root_logger.handlers.clear()

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        handlers=[
            logging.FileHandler(log_file),
            logging.StreamHandler(sys.stdout)
        ],
        force=True
    )
    logging.info(f"Logging initialized: {log_file}")


def main() -> int:
    setup_logging()

    print("=" * 70)
    print(f"{config.APP_NAME} v{config.APP_VERSION}")
    print("=" * 70)

    app = QApplication(sys.argv)
    app.setStyle("Fusion")

    controller = ApplicationController()
    if not controller.initialize():
        controller.shutdown()
        return 1

    exit_code = app.exec()
    controller.shutdown()
    return exit_code


if __name__ == "__main__":
    sys.exit(main())
