from pathlib import Path

import cv2
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QLabel
)
from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtGui import QImage, QPixmap

from device_drivers.thorlabs_camera_wrapper import ThorlabsCamera
from image_processing.image_position_check import detect_carbon_plate


class ThorlabsControlPanel(QWidget):
    """Control panel for Thorlabs camera: connect, live, capture, position check."""

    def __init__(self, parent=None):
        super().__init__(parent)

        self.camera = ThorlabsCamera()
        self.timer = QTimer(self)
        self.timer.timeout.connect(self._update_live_view)
        self._live_running = False

        self.save_dir = Path(r"C:\Users\Monster\Desktop\tez\GC-Pics\camPic")
        self.save_dir.mkdir(parents=True, exist_ok=True)

        self._build_ui()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(5, 5, 5, 5)
        layout.setSpacing(8)

        # Status
        self.status_label = QLabel("Camera status: disconnected")
        self.status_label.setAlignment(Qt.AlignmentFlag.AlignLeft)
        layout.addWidget(self.status_label)

        # Row 1: connect, live, capture
        row1 = QHBoxLayout()

        self.connect_btn = QPushButton("Connect")
        self.connect_btn.clicked.connect(self._on_connect)
        row1.addWidget(self.connect_btn)

        self.live_btn = QPushButton("Start live")
        self.live_btn.clicked.connect(self._on_toggle_live)
        row1.addWidget(self.live_btn)

        self.capture_btn = QPushButton("Capture && save")
        self.capture_btn.clicked.connect(self._on_capture)
        row1.addWidget(self.capture_btn)

        layout.addLayout(row1)

        # Row 2: position check, adjustment (stub), bubble recognition (stub)
        row2 = QHBoxLayout()

        self.position_btn = QPushButton("Image position check")
        self.position_btn.clicked.connect(self._on_position_check)
        row2.addWidget(self.position_btn)

        self.adjust_btn = QPushButton("Adjustment (stage)")
        # Later: connect to XYZStage using move_hint
        row2.addWidget(self.adjust_btn)

        self.bubble_btn = QPushButton("Bubble recognition")
        # Later: connect to image_recognition.py
        row2.addWidget(self.bubble_btn)

        layout.addLayout(row2)

        # Image display
        self.image_label = QLabel("Live image / results")
        self.image_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.image_label.setMinimumSize(320, 240)
        self.image_label.setStyleSheet("background-color: #202020; color: #AAAAAA;")
        layout.addWidget(self.image_label)

        # Result text
        self.result_label = QLabel("Result: N/A")
        self.result_label.setAlignment(Qt.AlignmentFlag.AlignLeft)
        layout.addWidget(self.result_label)

        layout.addStretch(1)

    # ---------- Button handlers ----------

    def _on_connect(self):
        try:
            self.camera.connect()
            self.status_label.setText("Camera status: connected")
        except Exception as e:
            self.status_label.setText(f"Error: {e}")

    def _on_toggle_live(self):
        if not self._live_running:
            try:
                if not self.camera._connected:
                    self.camera.connect()
                self.timer.start(100)  # 10 fps
                self._live_running = True
                self.live_btn.setText("Stop live")
                self.status_label.setText("Camera status: live")
            except Exception as e:
                self.status_label.setText(f"Error: {e}")
        else:
            self.timer.stop()
            self._live_running = False
            self.live_btn.setText("Start live")
            self.status_label.setText("Camera status: connected")

    def _on_capture(self):
        try:
            if not self.camera._connected:
                self.camera.connect()

            filename = self.save_dir / "capture.png"
            frame = self.camera.save_frame(str(filename))
            self._show_frame(frame)
            self.result_label.setText(f"Saved: {filename}")
        except Exception as e:
            self.result_label.setText(f"Error: {e}")

    def _on_position_check(self):
        """Capture a frame, run detect_carbon_plate, show annotated image + hint."""
        try:
            if not self.camera._connected:
                self.camera.connect()

            frame = self.camera.grab_frame()
            tmp_path = self.save_dir / "position_check.png"
            cv2.imwrite(str(tmp_path), frame)

            result = detect_carbon_plate(
                image_path=str(tmp_path),
                save_path=str(self.save_dir / "position_marked.png"),
                display_result=False
            )

            self._show_frame(result['output_image'])

            hint = result.get('move_hint', 'no_hint')
            if hint == 'ok':
                text = "Plate in frame: OK"
            elif hint == 'no_plate_found':
                text = "Plate not found – check sample / lighting"
            else:
                text = f"Plate off-center: {hint}"

            self.result_label.setText(f"Result: {text}")
        except Exception as e:
            self.result_label.setText(f"Error: {e}")

    # ---------- Helpers ----------

    def _update_live_view(self):
        try:
            frame = self.camera.grab_frame()
            self._show_frame(frame)
        except Exception as e:
            self.status_label.setText(f"Live error: {e}")
            self.timer.stop()
            self._live_running = False
            self.live_btn.setText("Start live")

    def _show_frame(self, frame_bgr):
        """Display a BGR OpenCV frame in the QLabel."""
        h, w, _ = frame_bgr.shape
        rgb = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2RGB)
        qimg = QImage(rgb.data, w, h, 3 * w, QImage.Format.Format_RGB888)
        pix = QPixmap.fromImage(qimg).scaled(
            self.image_label.width(),
            self.image_label.height(),
            Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation,
        )
        self.image_label.setPixmap(pix)
