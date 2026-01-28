import sys
from pathlib import Path

import cv2
import numpy as np

from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget,
    QHBoxLayout, QVBoxLayout, QPushButton, QLabel, QMessageBox, QTextEdit
)
from PySide6.QtGui import QPixmap, QImage
from PySide6.QtCore import Qt, QTimer
from device_drivers.we_detection import check_plate_spots
from PySide6.QtWidgets import QFileDialog

PROJECT_ROOT = Path(__file__).parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from device_drivers.PI_Control_System.app_factory import create_services
from device_drivers.PI_Control_System.core.models import Position
from device_drivers.plate_finder import gray_plate_on_red
from device_drivers.thorlabs_camera_wrapper import ThorlabsCamera
from device_drivers.plate_auto_adjuster import auto_adjust_plate

class SimpleStageApp(QMainWindow):
    def __init__(self, use_mock: bool = True):
        super().__init__()

        # --- PI services (no PI GUI) ---
        event_bus, connection_service, motion_service, config = create_services(use_mock=use_mock)
        self.event_bus = event_bus
        self.connection_service = connection_service
        self.motion_service = motion_service

        # --- Thorlabs camera wrapper ---
        TL_DLL_DIR = r"C:\Program Files\Thorlabs\ThorImageCAM\Bin"
        self.camera = ThorlabsCamera(dll_dir=TL_DLL_DIR)
        self.live_timer = QTimer(self)
        self.live_timer.timeout.connect(self._update_live_view)
        self.live_running = False

        # path of last captured image
        self.last_image_path: str | None = None

        # Positions
        self.park_position = Position(x=200.0, y=200.0, z=200.0)
        self.default_position = Position(x=150.0, y=150.0, z=150.0)

        # --- window + layout ---
        self.setWindowTitle("CTA – Stage + Plate Check")
        self.resize(1400, 800)

        central = QWidget()
        outer_layout = QVBoxLayout(central)
        outer_layout.setContentsMargins(5, 5, 5, 5)
        outer_layout.setSpacing(5)
        self.setCentralWidget(central)

        # Top: main area (left buttons + right image)
        top_layout = QHBoxLayout()
        outer_layout.addLayout(top_layout, stretch=3)

        # LEFT: buttons
        left_panel = QVBoxLayout()
        top_layout.addLayout(left_panel, stretch=1)

        # Connection status label
        self.status_label = QLabel("Stage status: DISCONNECTED")
        left_panel.addWidget(self.status_label)


        self.btn_connect = QPushButton("1. Connect (stage + camera)")
        self.btn_init = QPushButton("2. Initialize (park 200,200,200)")
        self.btn_cam_start = QPushButton("3. Camera Start (live)")
        self.btn_capture = QPushButton("4. Take a Picture")
        self.btn_plate = QPushButton("5. Plate detection")
        self.btn_adjust = QPushButton("6. Auto Adjust Stage")
        self.btn_we = QPushButton("7. WE Detection (TBD)")

        left_panel.addWidget(self.btn_connect)
        left_panel.addWidget(self.btn_init)
        left_panel.addWidget(self.btn_cam_start)
        left_panel.addWidget(self.btn_capture)
        left_panel.addWidget(self.btn_plate)
        left_panel.addWidget(self.btn_adjust)
        left_panel.addWidget(self.btn_we)
        left_panel.addStretch()

        # RIGHT: image display
        self.image_label = QLabel("Live / captured / processed image will appear here")
        self.image_label.setAlignment(Qt.AlignCenter)
        self.image_label.setStyleSheet("background-color: #202020; color: white;")
        top_layout.addWidget(self.image_label, stretch=2)

        # BOTTOM: log/output
        self.log_widget = QTextEdit()
        self.log_widget.setReadOnly(True)
        self.log_widget.setPlaceholderText("Log output will appear here...")
        outer_layout.addWidget(self.log_widget, stretch=1)

        # Connect buttons to handlers
        self.btn_connect.clicked.connect(self.on_connect_clicked)
        self.btn_init.clicked.connect(self.on_initialize_clicked)
        self.btn_cam_start.clicked.connect(self.on_cam_start_clicked)
        self.btn_capture.clicked.connect(self.on_capture_clicked)
        self.btn_plate.clicked.connect(self.on_plate_clicked)
        self.btn_adjust.clicked.connect(self.on_adjust_clicked)
        self.btn_we.clicked.connect(self.on_we_clicked)

    # ---------- logging helper ----------

    def log(self, message: str, level: str = "info"):
        prefix = {
            "info": "[INFO]",
            "warn": "[WARN]",
            "error": "[ERROR]"
        }.get(level, "[INFO]")
        self.log_widget.append(f"{prefix} {message}")

    # ---------- image helper ----------

    def cv_to_qpixmap(self, img_bgr: np.ndarray) -> QPixmap:
        img_rgb = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2RGB)
        h, w, ch = img_rgb.shape
        bytes_per_line = ch * w
        qimg = QImage(img_rgb.data, w, h, bytes_per_line, QImage.Format_RGB888)
        pix = QPixmap.fromImage(qimg)
        # scale to fit label while keeping aspect
        return pix.scaled(
            self.image_label.width(),
            self.image_label.height(),
            Qt.KeepAspectRatio,
            Qt.SmoothTransformation,
        )

    # ---------- button handlers (stubs + basic behavior) ----------

    def on_connect_clicked(self):
        try:
            self.connection_service.connect()
            self.status_label.setText(f"Stage status: {self.connection_service.state.connection.name}")
            self.log("Stage: connect() requested", "info")
        except Exception as e:
            self.status_label.setText("Stage status: ERROR")
            self.log(f"Stage connect error: {e}", "error")

    def on_initialize_clicked(self):
        try:
            self.connection_service.initialize()
            future = self.motion_service.move_to_position_safe_z(self.park_position)
            future.result(timeout=60)

            self.status_label.setText(f"Stage status: {self.connection_service.state.connection.name}")
            self.log("Stage initialized and parked at 200,200,200.", "info")
        except Exception as e:
            self.status_label.setText("Stage status: ERROR")
            self.log(f"Initialize error: {e}", "error")
            QMessageBox.critical(self, "Initialize error", str(e))

    def on_cam_start_clicked(self):
        """3- Camera Start: toggle live view."""
        if not self.live_running:
            try:
                if not self.camera._connected:
                    self.camera.connect()
                self.live_timer.start(100)  # ~10 fps
                self.live_running = True
                self.btn_cam_start.setText("3. Camera Stop (live)")
                self.log("Camera live started", "info")
            except Exception as e:
                self.log(f"Live start error: {e}", "error")
        else:
            self.live_timer.stop()
            self.live_running = False
            self.btn_cam_start.setText("3. Camera Start (live)")
            self.log("Camera live stopped", "info")

    def on_capture_clicked(self):
        """4- Take a Picture: capture one frame and show it."""
        try:
            if not self.camera._connected:
                self.camera.connect()

            save_dir = PROJECT_ROOT / "artifacts" / "captures"
            save_dir.mkdir(parents=True, exist_ok=True)
            filename = save_dir / "capture.png"

            frame = self.camera.save_frame(str(filename))
            self.last_image_path = str(filename)

            pix = self.cv_to_qpixmap(frame)
            self.image_label.setPixmap(pix)

            self.log(f"Captured image: {filename}", "info")
        except Exception as e:
            self.log(f"Capture error: {e}", "error")
            QMessageBox.critical(self, "Capture error", str(e))

    def on_plate_clicked(self):
        """5- Plate detection on last captured image or user-chosen file."""
        image_path = self.last_image_path

        if not image_path:
            # Ask user to choose an image
            file_path, _ = QFileDialog.getOpenFileName(
                self,
                "Select image for plate detection",
                str(PROJECT_ROOT),
                "Images (*.png *.jpg *.jpeg *.bmp)",
            )
            if not file_path:
                self.log("Plate detection cancelled (no image).", "warn")
                return
            image_path = file_path
            self.log(f"Using user-selected image: {image_path}", "info")

        try:
            result = gray_plate_on_red(image_path, margin_frac=0.02, debug=False)
            bbox = result["rect_bbox"]
            output_img = result["output_display"]
            fully = result["fully_in_frame"]
            hint = result["move_hint"]
            save_path = result["save_path"]

            if output_img is not None:
                pix = self.cv_to_qpixmap(output_img)
                self.image_label.setPixmap(pix)

            if not bbox:
                msg = f"No plate detected. hint={hint}, saved={save_path}"
                self.log(msg, "warn")
                QMessageBox.warning(self, "Plate detection", msg)
            else:
                if fully:
                    msg = f"Plate fully in frame (Yes). hint={hint}, saved={save_path}"
                    self.log(msg, "info")
                    QMessageBox.information(self, "Plate detection", msg)
                else:
                    msg = f"Plate NOT fully in frame (No). hint={hint}, saved={save_path}"
                    self.log(msg, "warn")
                    QMessageBox.warning(self, "Plate detection", msg)
        except Exception as e:
            self.log(f"Plate detection error: {e}", "error")
            QMessageBox.critical(self, "Plate detection error", str(e))

    def on_adjust_clicked(self):
        """6- Auto Adjust Stage: loop capture + detect + move."""
        try:
            # Ensure camera is connected
            if not self.camera._connected:
                self.camera.connect()

            save_dir = PROJECT_ROOT / "artifacts" / "auto_adjust"
            fully, final_hint, steps_log = auto_adjust_plate(
                motion_service=self.motion_service,
                camera=self.camera,
                save_dir=save_dir,
                step_mm=5.0,
                max_iterations=10,
            )

            for line in steps_log:
                # steps_log already has prefixes; treat as info
                self.log(line, "info")

            if fully:
                msg = f"Auto-adjust succeeded. final_hint={final_hint}"
                self.log(msg, "info")
                QMessageBox.information(self, "Auto Adjust", msg)
            else:
                msg = f"Auto-adjust did not fully succeed. final_hint={final_hint}"
                self.log(msg, "warn")
                QMessageBox.warning(self, "Auto Adjust", msg)

        except Exception as e:
            self.log(f"Auto adjust error: {e}", "error")
            QMessageBox.critical(self, "Auto Adjust error", str(e))


    def on_we_clicked(self):
        """7- WE Detection (bubble/spot check)."""
        # Prefer last captured image; otherwise let user choose
        image_path = self.last_image_path

        if not image_path:
            file_path, _ = QFileDialog.getOpenFileName(
                self,
                "Select image for WE (bubble) detection",
                str(PROJECT_ROOT),
                "Images (*.png *.jpg *.jpeg *.bmp)",
            )
            if not file_path:
                self.log("WE detection cancelled (no image).", "warn")
                return
            image_path = file_path
            self.log(f"WE detection using user-selected image: {image_path}", "info")
        else:
            self.log(f"WE detection using last captured image: {image_path}", "info")

        try:
            save_dir = PROJECT_ROOT / "artifacts" / "we_detection"
            save_dir.mkdir(parents=True, exist_ok=True)
            save_path = save_dir / "we_checked.png"

            result = check_plate_spots(
                image_path=image_path,
                save_path=str(save_path),
                display_result=False
            )

            output_img = result["output_image"]
            perfect = result["perfect_circle_count"]
            defective = result["defective_count"]

            if output_img is not None:
                pix = self.cv_to_qpixmap(output_img)
                self.image_label.setPixmap(pix)

            msg = (
                f"WE detection:\n"
                f"  perfect circles: {perfect}\n"
                f"  defective spots: {defective}\n"
                f"  saved: {save_path}"
            )
            level = "info" if defective == 0 else "warn"
            self.log(msg, level)

            if defective == 0:
                QMessageBox.information(self, "WE Detection", msg)
            else:
                QMessageBox.warning(self, "WE Detection", msg)

        except Exception as e:
            self.log(f"WE detection error: {e}", "error")
            QMessageBox.critical(self, "WE Detection error", str(e))


    # ---------- live view helper ----------

    def _update_live_view(self):
        try:
            frame = self.camera.grab_frame()
            pix = self.cv_to_qpixmap(frame)
            self.image_label.setPixmap(pix)
        except Exception as e:
            self.log(f"Live view error: {e}", "error")
            self.live_timer.stop()
            self.live_running = False
            self.btn_cam_start.setText("3. Camera Start (live)")


def main():
    app = QApplication(sys.argv)
    window = SimpleStageApp(use_mock=False)
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
