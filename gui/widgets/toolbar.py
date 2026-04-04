from PySide6.QtWidgets import QWidget, QHBoxLayout, QPushButton, QLabel
from PySide6.QtCore import Signal


class WorkflowToolbar(QWidget):
    """Top toolbar with workflow buttons and status indicator."""

    connect_clicked = Signal()
    initialize_clicked = Signal()
    camera_toggled = Signal()
    capture_clicked = Signal()
    plate_detect_clicked = Signal()
    auto_adjust_clicked = Signal()
    we_detect_clicked = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(6)

        # Status indicator
        self.status_label = QLabel("● DISCONNECTED")
        self.status_label.setStyleSheet("""
            QLabel {
                color: #ff6b6b;
                font-weight: bold;
                padding: 6px 12px;
                background-color: #2a2a2a;
                border-radius: 4px;
                min-width: 140px;
            }
        """)
        layout.addWidget(self.status_label)
        layout.addSpacing(10)

        btn_style = """
            QPushButton {
                padding: 8px 16px;
                font-weight: bold;
                border-radius: 4px;
                min-width: 80px;
            }
            QPushButton:hover {
                background-color: #4a4a4a;
            }
            QPushButton:pressed {
                background-color: #3a3a3a;
            }
        """

        self.btn_connect = QPushButton("Connect")
        self.btn_init = QPushButton("Initialize")
        self.btn_cam_start = QPushButton("Camera")
        self.btn_capture = QPushButton("Capture")
        self.btn_plate = QPushButton("Plate Detect")
        self.btn_adjust = QPushButton("Auto Adjust")
        self.btn_we = QPushButton("WE Detect")

        for btn in [self.btn_connect, self.btn_init, self.btn_cam_start,
                    self.btn_capture, self.btn_plate, self.btn_adjust, self.btn_we]:
            btn.setStyleSheet(btn_style)
            layout.addWidget(btn)

        layout.addStretch()

        # Wire internal signals
        self.btn_connect.clicked.connect(self.connect_clicked.emit)
        self.btn_init.clicked.connect(self.initialize_clicked.emit)
        self.btn_cam_start.clicked.connect(self.camera_toggled.emit)
        self.btn_capture.clicked.connect(self.capture_clicked.emit)
        self.btn_plate.clicked.connect(self.plate_detect_clicked.emit)
        self.btn_adjust.clicked.connect(self.auto_adjust_clicked.emit)
        self.btn_we.clicked.connect(self.we_detect_clicked.emit)

    def set_status(self, text: str, state: str = "disconnected"):
        colors = {
            "disconnected": "#ff6b6b",
            "connecting": "#ffd93d",
            "ready": "#6bcb77",
            "error": "#ff6b6b",
        }
        color = colors.get(state, "#ff6b6b")
        self.status_label.setText(f"● {text}")
        self.status_label.setStyleSheet(f"""
            QLabel {{
                color: {color};
                font-weight: bold;
                padding: 6px 12px;
                background-color: #2a2a2a;
                border-radius: 4px;
                min-width: 140px;
            }}
        """)
