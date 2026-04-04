"""
System log widget for displaying event messages.

Source: legacy/PI_Control_GUI/main_gui.py status display
"""

from PySide6.QtWidgets import QWidget, QVBoxLayout, QTextEdit, QLabel
from PySide6.QtCore import Qt
from PySide6.QtGui import QFont, QTextCursor
from datetime import datetime


class SystemLogWidget(QWidget):
    """Widget displaying chronological system log.

    Controller layer appends messages when events occur.
    No direct EventBus subscription - keeps widget testable.
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self._setup_ui()

    def _setup_ui(self):
        """Build UI layout."""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)

        # Title
        title = QLabel("System Log")
        title.setFont(QFont("Segoe UI", 12, QFont.Bold))
        title.setStyleSheet("color: #e2e8f0;")
        layout.addWidget(title)

        # Log text area
        self.log_text = QTextEdit()
        self.log_text.setReadOnly(True)
        self.log_text.setStyleSheet("""
            QTextEdit {
                background: rgba(0,0,0,0.4);
                color: #cbd5e0;
                border: 1px solid rgba(99, 179, 194, 0.2);
                border-radius: 4px;
                padding: 8px;
                font-family: Consolas, monospace;
                font-size: 10pt;
            }
        """)
        self.log_text.setMaximumHeight(200)
        layout.addWidget(self.log_text)

    def append_message(self, message: str, level: str = "info"):
        """Append a message to the log.

        Args:
            message: Message text
            level: Message level (info, warning, error, success)
        """
        timestamp = datetime.now().strftime("%H:%M:%S")

        colors = {
            "info": "#cbd5e0",
            "warning": "#f6ad55",
            "error": "#fc8181",
            "success": "#68d391"
        }
        color = colors.get(level, "#cbd5e0")

        formatted = f'<span style="color: #a0aec0;">[{timestamp}]</span> <span style="color: {color};">{message}</span>'

        self.log_text.append(formatted)

        # Auto-scroll to bottom
        cursor = self.log_text.textCursor()
        cursor.movePosition(QTextCursor.End)
        self.log_text.setTextCursor(cursor)

    def clear(self):
        """Clear all log messages."""
        self.log_text.clear()
