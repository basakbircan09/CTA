import sys
from pathlib import Path

import cv2
import numpy as np

from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget,
    QHBoxLayout, QVBoxLayout, QPushButton, QLabel, QMessageBox, QTextEdit,
    QFileDialog, QGroupBox, QGridLayout, QDoubleSpinBox, QSpinBox, QComboBox
)
from PySide6.QtGui import QPixmap, QImage
from PySide6.QtCore import Qt, QTimer
from device_drivers.PI_Control_System.core.models import Axis

PROJECT_ROOT = Path(__file__).parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from device_drivers.PI_Control_System.app_factory import create_services
from device_drivers.PI_Control_System.core.models import Position
from device_drivers.thorlabs_camera_wrapper import ThorlabsCamera
from device_drivers.plate_auto_adjuster import auto_adjust_plate
from device_drivers.GPT_Merge import analyze_plate_and_spots

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
        # path of last detected plate image
        self.last_plate_path: str | None = None

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

        # --- Camera Settings Panel ---
        cam_group = QGroupBox("Camera Settings")
        cam_layout = QGridLayout(cam_group)

        cam_layout.addWidget(QLabel("Exposure (ms):"), 0, 0)
        self.spin_exposure = QDoubleSpinBox()
        self.spin_exposure.setRange(1.0, 5000.0)
        self.spin_exposure.setValue(100.0)
        self.spin_exposure.setSingleStep(10.0)
        self.spin_exposure.setDecimals(1)
        cam_layout.addWidget(self.spin_exposure, 0, 1)
        self.btn_set_exposure = QPushButton("Set")
        self.btn_set_exposure.clicked.connect(self.on_set_exposure)
        cam_layout.addWidget(self.btn_set_exposure, 0, 2)

        cam_layout.addWidget(QLabel("Gain:"), 1, 0)
        self.spin_gain = QDoubleSpinBox()
        self.spin_gain.setRange(0.0, 48.0)
        self.spin_gain.setValue(0.0)
        self.spin_gain.setSingleStep(1.0)
        self.spin_gain.setDecimals(1)
        cam_layout.addWidget(self.spin_gain, 1, 1)
        self.btn_set_gain = QPushButton("Set")
        self.btn_set_gain.clicked.connect(self.on_set_gain)
        cam_layout.addWidget(self.btn_set_gain, 1, 2)

        # White Balance presets
        cam_layout.addWidget(QLabel("White Bal:"), 2, 0)
        self.combo_wb = QComboBox()
        self.combo_wb.addItems(["Default", "Warm", "Cool", "Reduce NIR", "Custom"])
        self.combo_wb.currentTextChanged.connect(self.on_wb_preset_changed)
        cam_layout.addWidget(self.combo_wb, 2, 1, 1, 2)

        # White Balance RGB sliders (for Custom)
        cam_layout.addWidget(QLabel("R:"), 3, 0)
        self.spin_wb_r = QDoubleSpinBox()
        self.spin_wb_r.setRange(0.1, 4.0)
        self.spin_wb_r.setValue(1.0)
        self.spin_wb_r.setSingleStep(0.1)
        self.spin_wb_r.setDecimals(2)
        cam_layout.addWidget(self.spin_wb_r, 3, 1, 1, 2)

        cam_layout.addWidget(QLabel("G:"), 4, 0)
        self.spin_wb_g = QDoubleSpinBox()
        self.spin_wb_g.setRange(0.1, 4.0)
        self.spin_wb_g.setValue(1.0)
        self.spin_wb_g.setSingleStep(0.1)
        self.spin_wb_g.setDecimals(2)
        cam_layout.addWidget(self.spin_wb_g, 4, 1, 1, 2)

        cam_layout.addWidget(QLabel("B:"), 5, 0)
        self.spin_wb_b = QDoubleSpinBox()
        self.spin_wb_b.setRange(0.1, 4.0)
        self.spin_wb_b.setValue(1.0)
        self.spin_wb_b.setSingleStep(0.1)
        self.spin_wb_b.setDecimals(2)
        cam_layout.addWidget(self.spin_wb_b, 5, 1, 1, 2)

        self.btn_apply_wb = QPushButton("Apply WB")
        self.btn_apply_wb.clicked.connect(self.on_apply_white_balance)
        cam_layout.addWidget(self.btn_apply_wb, 6, 0, 1, 3)

        left_panel.addWidget(cam_group)

        # --- Stage Control Panel ---
        stage_group = QGroupBox("Stage Control")
        stage_layout = QVBoxLayout(stage_group)

        # Current position display
        self.pos_label = QLabel("Position: X=?.?? Y=?.?? Z=?.??")
        stage_layout.addWidget(self.pos_label)

        # Step size control
        step_layout = QHBoxLayout()
        step_layout.addWidget(QLabel("Step (mm):"))
        self.spin_step = QDoubleSpinBox()
        self.spin_step.setRange(0.1, 50.0)
        self.spin_step.setValue(5.0)
        self.spin_step.setSingleStep(1.0)
        self.spin_step.setDecimals(1)
        step_layout.addWidget(self.spin_step)
        self.btn_refresh_pos = QPushButton("Refresh")
        self.btn_refresh_pos.clicked.connect(self.on_refresh_position)
        step_layout.addWidget(self.btn_refresh_pos)
        stage_layout.addLayout(step_layout)

        # Jog buttons grid: X, Y, Z with +/-
        jog_grid = QGridLayout()
        jog_grid.addWidget(QLabel("X:"), 0, 0)
        self.btn_x_minus = QPushButton("-")
        self.btn_x_plus = QPushButton("+")
        self.btn_x_minus.clicked.connect(lambda: self.on_jog_axis(Axis.X, -1))
        self.btn_x_plus.clicked.connect(lambda: self.on_jog_axis(Axis.X, 1))
        jog_grid.addWidget(self.btn_x_minus, 0, 1)
        jog_grid.addWidget(self.btn_x_plus, 0, 2)

        jog_grid.addWidget(QLabel("Y:"), 1, 0)
        self.btn_y_minus = QPushButton("-")
        self.btn_y_plus = QPushButton("+")
        self.btn_y_minus.clicked.connect(lambda: self.on_jog_axis(Axis.Y, -1))
        self.btn_y_plus.clicked.connect(lambda: self.on_jog_axis(Axis.Y, 1))
        jog_grid.addWidget(self.btn_y_minus, 1, 1)
        jog_grid.addWidget(self.btn_y_plus, 1, 2)

        jog_grid.addWidget(QLabel("Z:"), 2, 0)
        self.btn_z_minus = QPushButton("-")
        self.btn_z_plus = QPushButton("+")
        self.btn_z_minus.clicked.connect(lambda: self.on_jog_axis(Axis.Z, -1))
        self.btn_z_plus.clicked.connect(lambda: self.on_jog_axis(Axis.Z, 1))
        jog_grid.addWidget(self.btn_z_minus, 2, 1)
        jog_grid.addWidget(self.btn_z_plus, 2, 2)

        stage_layout.addLayout(jog_grid)

        # Absolute position entry
        abs_grid = QGridLayout()
        abs_grid.addWidget(QLabel("Go to:"), 0, 0, 1, 3)

        abs_grid.addWidget(QLabel("X:"), 1, 0)
        self.spin_goto_x = QDoubleSpinBox()
        self.spin_goto_x.setRange(0.0, 300.0)
        self.spin_goto_x.setValue(200.0)
        self.spin_goto_x.setDecimals(2)
        abs_grid.addWidget(self.spin_goto_x, 1, 1, 1, 2)

        abs_grid.addWidget(QLabel("Y:"), 2, 0)
        self.spin_goto_y = QDoubleSpinBox()
        self.spin_goto_y.setRange(0.0, 300.0)
        self.spin_goto_y.setValue(200.0)
        self.spin_goto_y.setDecimals(2)
        abs_grid.addWidget(self.spin_goto_y, 2, 1, 1, 2)

        abs_grid.addWidget(QLabel("Z:"), 3, 0)
        self.spin_goto_z = QDoubleSpinBox()
        self.spin_goto_z.setRange(0.0, 300.0)
        self.spin_goto_z.setValue(200.0)
        self.spin_goto_z.setDecimals(2)
        abs_grid.addWidget(self.spin_goto_z, 3, 1, 1, 2)

        self.btn_goto = QPushButton("Go to Position")
        self.btn_goto.clicked.connect(self.on_goto_position)
        abs_grid.addWidget(self.btn_goto, 4, 0, 1, 3)

        stage_layout.addLayout(abs_grid)

        left_panel.addWidget(stage_group)

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
            self.status_label.setText("Stage status: CONNECTING...")
            self.log("Stage: connecting to all controllers...", "info")

            future = self.connection_service.connect()
            future.result(timeout=30)  # Wait for connection to complete

            self.status_label.setText(f"Stage status: {self.connection_service.state.connection.name}")
            self.log("Stage: all controllers connected successfully", "info")
        except Exception as e:
            self.status_label.setText("Stage status: ERROR")
            self.log(f"Stage connect error: {e}", "error")
            QMessageBox.critical(self, "Connection error", str(e))

    def on_initialize_clicked(self):
        try:
            # Check if connected first
            if not self.connection_service.state.connection.name == "CONNECTED":
                QMessageBox.warning(self, "Not Connected",
                    "Please connect to controllers first (Step 1).")
                return

            self.status_label.setText("Stage status: INITIALIZING...")
            self.log("Stage: initializing and referencing all axes...", "info")

            # Wait for initialization to complete
            init_future = self.connection_service.initialize()
            init_future.result(timeout=120)  # Referencing can take time

            self.log("Stage: initialization complete, moving to park position...", "info")

            # Now move to park position
            move_future = self.motion_service.move_to_position_safe_z(self.park_position)
            move_future.result(timeout=60)

            self.status_label.setText(f"Stage status: {self.connection_service.state.connection.name}")
            self.log(f"Stage initialized and parked at {self.park_position}.", "info")
        except Exception as e:
            self.status_label.setText("Stage status: ERROR")
            self.log(f"Initialize error: {e}", "error")
            QMessageBox.critical(self, "Initialize error", str(e))

    def on_cam_start_clicked(self):
        """3- Camera Start: toggle live view."""
        if not self.live_running:
            try:
                if not self.camera.is_connected:
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
            if not self.camera.is_connected:
                self.camera.connect()

            save_dir = PROJECT_ROOT / "artifacts" / "captures"
            save_dir.mkdir(parents=True, exist_ok=True)

            # Build filename from current settings
            exp = self.spin_exposure.value()
            gain = self.spin_gain.value()
            r = self.spin_wb_r.value()
            g = self.spin_wb_g.value()
            b = self.spin_wb_b.value()

            base_name = f"Photo_{exp:.1f}_{gain:.1f}_{r:.2f}_{g:.2f}_{b:.2f}"

            # Find unique filename with incrementing suffix
            filename = save_dir / f"{base_name}.png"
            counter = 1
            while filename.exists():
                filename = save_dir / f"{base_name}_{counter}.png"
                counter += 1

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
            save_dir = PROJECT_ROOT / "artifacts" / "plate_detection"
            save_dir.mkdir(parents=True, exist_ok=True)
            result = analyze_plate_and_spots(image_path, str(save_dir))

            if result["error"]:
                msg = f"Detection error: {result['error']}"
                self.log(msg, "warn")
                QMessageBox.warning(self, "Plate detection", msg)
                return

            if not result["plate_detected"]:
                msg = "No plate detected in image."
                self.log(msg, "warn")
                QMessageBox.warning(self, "Plate detection", msg)
                return

            # Save and display just the cropped plate image
            plate_img = result["plate_image"]
            plate_path = save_dir / "plate.png"
            cv2.imwrite(str(plate_path), plate_img)
            self.last_plate_path = str(plate_path)

            pix = self.cv_to_qpixmap(plate_img)
            self.image_label.setPixmap(pix)

            bbox = result["plate_bbox"]
            msg = f"Plate detected at {bbox}\nSaved to: {plate_path}"
            self.log(msg, "info")
            QMessageBox.information(self, "Plate detection", msg)
        except Exception as e:
            self.log(f"Plate detection error: {e}", "error")
            QMessageBox.critical(self, "Plate detection error", str(e))

    def on_adjust_clicked(self):
        """6- Auto Adjust Stage: loop capture + detect + move."""
        if not self._is_stage_ready():
            QMessageBox.warning(self, "Stage Not Ready",
                "Please connect and initialize the stage first.")
            return
        try:
            # Ensure camera is connected
            if not self.camera.is_connected:
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
        """7- WE Detection (bubble/spot check) on detected plate image."""
        # Prefer last detected plate image; otherwise let user choose
        image_path = self.last_plate_path

        if not image_path:
            # No plate detected yet, ask user if they want to select an image
            msg = "No plate detected yet. Please run Plate Detection first, or select an image manually."
            self.log(msg, "warn")
            reply = QMessageBox.question(
                self,
                "WE Detection",
                msg + "\n\nWould you like to select an image manually?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
            )
            if reply == QMessageBox.StandardButton.Yes:
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
                return
        else:
            self.log(f"WE detection using detected plate image: {image_path}", "info")

        try:
            save_dir = PROJECT_ROOT / "artifacts" / "we_detection"
            result = analyze_plate_and_spots(image_path, str(save_dir))

            if result["error"]:
                msg = f"Detection error: {result['error']}"
                self.log(msg, "warn")
                QMessageBox.warning(self, "WE Detection", msg)
                return

            # Show accepted spots image (spots without defects)
            output_img = result["accepted_spots_image"]
            if output_img is not None:
                pix = self.cv_to_qpixmap(output_img)
                self.image_label.setPixmap(pix)

            accepted = len(result["accepted_spots"])
            rejected = len(result["rejected_spots"])
            total = len(result["all_spots"])

            # List rejected spot labels
            rejected_labels = [s.get("label", "?") for s in result["rejected_spots"]]

            msg = (
                f"WE Detection Results:\n"
                f"  Total spots: {total}\n"
                f"  Accepted (no defects): {accepted}\n"
                f"  Rejected (bubbles/holes): {rejected}\n"
            )
            if rejected_labels:
                msg += f"  Defective spots: {', '.join(rejected_labels)}"

            level = "info" if rejected == 0 else "warn"
            self.log(msg, level)

            if rejected == 0:
                QMessageBox.information(self, "WE Detection", msg)
            else:
                QMessageBox.warning(self, "WE Detection", msg)

        except Exception as e:
            self.log(f"WE detection error: {e}", "error")
            QMessageBox.critical(self, "WE Detection error", str(e))


    # ---------- camera settings handlers ----------

    def on_set_exposure(self):
        """Set camera exposure from spinbox value (ms -> seconds)."""
        try:
            if not self.camera.is_connected:
                self.log("Camera not connected", "warn")
                return
            exposure_ms = self.spin_exposure.value()
            exposure_sec = exposure_ms / 1000.0
            self.camera.set_exposure(exposure_sec)
            self.log(f"Exposure set to {exposure_ms:.1f} ms", "info")
        except Exception as e:
            self.log(f"Set exposure error: {e}", "error")

    def on_set_gain(self):
        """Set camera gain from spinbox value."""
        try:
            if not self.camera.is_connected:
                self.log("Camera not connected", "warn")
                return
            gain = self.spin_gain.value()
            self.camera.set_gain(gain)
            self.log(f"Gain set to {gain:.1f}", "info")
        except Exception as e:
            self.log(f"Set gain error: {e}", "error")

    def on_wb_preset_changed(self, preset: str):
        """Update RGB spinboxes when white balance preset changes."""
        presets = {
            "Default": (1.0, 1.0, 1.0),
            "Warm": (1.0, 0.9, 0.7),
            "Cool": (0.9, 1.0, 1.2),
            "Reduce NIR": (0.6, 0.8, 1.0),
            "Custom": None  # Don't change spinboxes for custom
        }
        if preset in presets and presets[preset] is not None:
            r, g, b = presets[preset]
            self.spin_wb_r.setValue(r)
            self.spin_wb_g.setValue(g)
            self.spin_wb_b.setValue(b)
            self.on_apply_white_balance()

    def on_apply_white_balance(self):
        """Apply white balance from RGB spinbox values."""
        try:
            r = self.spin_wb_r.value()
            g = self.spin_wb_g.value()
            b = self.spin_wb_b.value()
            self.camera.set_white_balance(r, g, b)
            self.log(f"White balance set to R={r:.2f} G={g:.2f} B={b:.2f}", "info")
        except Exception as e:
            self.log(f"Set white balance error: {e}", "error")

    # ---------- stage control handlers ----------

    def _is_stage_ready(self) -> bool:
        """Check if stage is connected and initialized."""
        return self.connection_service.is_ready()

    def on_refresh_position(self):
        """Refresh and display current stage position."""
        if not self._is_stage_ready():
            self.log("Cannot get position: stage not initialized", "warn")
            return
        try:
            pos = self.motion_service.get_current_position()
            self.pos_label.setText(f"Position: X={pos.x:.2f} Y={pos.y:.2f} Z={pos.z:.2f}")
            # Also update the goto spinboxes to current position
            self.spin_goto_x.setValue(pos.x)
            self.spin_goto_y.setValue(pos.y)
            self.spin_goto_z.setValue(pos.z)
            self.log(f"Position: X={pos.x:.2f} Y={pos.y:.2f} Z={pos.z:.2f}", "info")
        except Exception as e:
            self.log(f"Get position error: {e}", "error")

    def on_jog_axis(self, axis: Axis, direction: int):
        """Jog a single axis by step size in given direction (+1 or -1)."""
        if not self._is_stage_ready():
            QMessageBox.warning(self, "Stage Not Ready",
                "Please connect and initialize the stage first.")
            return
        try:
            step = self.spin_step.value() * direction
            self.log(f"Jogging {axis.value} by {step:+.1f} mm...", "info")
            future = self.motion_service.move_axis_relative(axis, step)
            future.result(timeout=30)
            self.on_refresh_position()
        except Exception as e:
            self.log(f"Jog {axis.value} error: {e}", "error")

    def on_goto_position(self):
        """Move stage to absolute position from spinbox values."""
        if not self._is_stage_ready():
            QMessageBox.warning(self, "Stage Not Ready",
                "Please connect and initialize the stage first.")
            return
        try:
            target = Position(
                x=self.spin_goto_x.value(),
                y=self.spin_goto_y.value(),
                z=self.spin_goto_z.value()
            )
            self.log(f"Moving to X={target.x:.2f} Y={target.y:.2f} Z={target.z:.2f}...", "info")
            future = self.motion_service.move_to_position_safe_z(target)
            future.result(timeout=60)
            self.on_refresh_position()
            self.log("Move complete.", "info")
        except Exception as e:
            self.log(f"Go to position error: {e}", "error")

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

    def closeEvent(self, event):
        """Clean up hardware connections when app closes."""
        self.log("Closing application, disconnecting hardware...", "info")

        # Stop live view
        if self.live_running:
            self.live_timer.stop()
            self.live_running = False

        # Disconnect camera
        try:
            if self.camera.is_connected:
                self.camera.disconnect()
        except Exception as e:
            print(f"Camera disconnect error: {e}")

        # Disconnect stage
        try:
            self.connection_service.shutdown()
        except Exception as e:
            print(f"Stage disconnect error: {e}")

        event.accept()


def main():
    app = QApplication(sys.argv)
    window = SimpleStageApp(use_mock=False)
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
