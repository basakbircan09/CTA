from PySide6.QtWidgets import QGroupBox, QVBoxLayout, QTextEdit


class LogPanel(QGroupBox):
    """Log output panel displaying timestamped messages."""

    def __init__(self, parent=None):
        super().__init__("Log", parent)
        self.setStyleSheet("QGroupBox { font-weight: bold; }")

        layout = QVBoxLayout(self)
        layout.setContentsMargins(4, 4, 4, 4)

        self.log_widget = QTextEdit()
        self.log_widget.setReadOnly(True)
        self.log_widget.setPlaceholderText("Log output will appear here...")
        self.log_widget.setMaximumHeight(120)
        self.log_widget.setStyleSheet("""
            QTextEdit {
                background-color: #1a1a1a;
                border: none;
                font-family: monospace;
                font-size: 11px;
            }
        """)
        layout.addWidget(self.log_widget)

    def log(self, message: str, level: str = "info"):
        prefix = {
            "info": "[INFO]",
            "warn": "[WARN]",
            "error": "[ERROR]"
        }.get(level, "[INFO]")
        self.log_widget.append(f"{prefix} {message}")
