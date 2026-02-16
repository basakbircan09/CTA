"""
Connection panel widget for hardware connection controls.

Source: legacy/PI_Control_GUI/main_gui.py connection controls
"""

from PySide6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QLabel, QFrame
from PySide6.QtCore import Signal, Qt
from PySide6.QtGui import QFont

from ...core.models import ConnectionState


class ConnectionPanel(QWidget):
    """Widget providing connect/initialize/disconnect controls.

    Emits signals for user actions; does NOT call services directly.
    Controller layer wires signals to service methods.

    Signals:
        connect_requested: User clicked Connect button
        initialize_requested: User clicked Initialize button
        disconnect_requested: User clicked Disconnect button
    """

    connect_requested = Signal()
    initialize_requested = Signal()
    disconnect_requested = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._setup_ui()
        self._current_state = ConnectionState.DISCONNECTED

    def _setup_ui(self):
        """Build UI layout."""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)

        # Title
        title = QLabel("Hardware Connection")
        title.setFont(QFont("Segoe UI", 12, QFont.Bold))
        title.setStyleSheet("color: #e2e8f0;")
        layout.addWidget(title)

        # Status label
        self.status_label = QLabel("Disconnected")
        self.status_label.setStyleSheet("""
            QLabel {
                color: #cbd5e0;
                padding: 8px;
                background: rgba(0,0,0,0.2);
                border-radius: 4px;
                font-size: 11pt;
            }
        """)
        layout.addWidget(self.status_label)

        # Buttons
        button_layout = QHBoxLayout()

        self.connect_btn = QPushButton("Connect")
        self.connect_btn.setStyleSheet(self._button_style("#38a169"))
        self.connect_btn.clicked.connect(self.connect_requested.emit)

        self.initialize_btn = QPushButton("Initialize")
        self.initialize_btn.setStyleSheet(self._button_style("#3182ce"))
        self.initialize_btn.setEnabled(False)
        self.initialize_btn.clicked.connect(self.initialize_requested.emit)

        self.disconnect_btn = QPushButton("Disconnect")
        self.disconnect_btn.setStyleSheet(self._button_style("#e53e3e"))
        self.disconnect_btn.setEnabled(False)
        self.disconnect_btn.clicked.connect(self.disconnect_requested.emit)

        button_layout.addWidget(self.connect_btn)
        button_layout.addWidget(self.initialize_btn)
        button_layout.addWidget(self.disconnect_btn)

        layout.addLayout(button_layout)

    def _button_style(self, color: str) -> str:
        """Generate button stylesheet."""
        return f"""
            QPushButton {{
                background-color: {color};
                color: white;
                border: none;
                padding: 10px 20px;
                border-radius: 6px;
                font-size: 11pt;
                font-weight: bold;
            }}
            QPushButton:hover {{
                background-color: {color}dd;
            }}
            QPushButton:disabled {{
                background-color: #4a5568;
                color: #a0aec0;
            }}
        """

    def update_state(self, state: ConnectionState):
        """Update UI based on connection state.

        Called by controller when state changes.

        Args:
            state: New connection state
        """
        self._current_state = state

        # Update status label
        state_text = {
            ConnectionState.DISCONNECTED: ("Disconnected", "#cbd5e0"),
            ConnectionState.CONNECTING: ("Connecting...", "#f6ad55"),
            ConnectionState.CONNECTED: ("Connected", "#68d391"),
            ConnectionState.INITIALIZING: ("Initializing...", "#f6ad55"),
            ConnectionState.READY: ("Ready", "#68d391"),
            ConnectionState.ERROR: ("Error", "#fc8181"),
        }

        text, color = state_text.get(state, ("Unknown", "#cbd5e0"))
        self.status_label.setText(text)
        self.status_label.setStyleSheet(f"""
            QLabel {{
                color: {color};
                padding: 8px;
                background: rgba(0,0,0,0.2);
                border-radius: 4px;
                font-size: 11pt;
                font-weight: bold;
            }}
        """)

        # Update button states
        self.connect_btn.setEnabled(state == ConnectionState.DISCONNECTED)
        self.initialize_btn.setEnabled(state == ConnectionState.CONNECTED)
        self.disconnect_btn.setEnabled(state in [
            ConnectionState.CONNECTED,
            ConnectionState.READY,
            ConnectionState.ERROR
        ])
