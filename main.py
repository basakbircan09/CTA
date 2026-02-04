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
        self.resize(1400, 850)

        central = QWidget()
        outer_layout = QVBoxLayout(central)
        outer_layout.setContentsMargins(8, 8, 8, 8)
        outer_layout.setSpacing(8)
        self.setCentralWidget(central)

        # ==================== TOP TOOLBAR ====================
        toolbar_layout = QHBoxLayout()
        toolbar_layout.setSpacing(6)

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
        toolbar_layout.addWidget(self.status_label)

        toolbar_layout.addSpacing(10)

        # Workflow buttons - styled
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
            toolbar_layout.addWidget(btn)

        toolbar_layout.addStretch()
        outer_layout.addLayout(toolbar_layout)

        # ==================== MIDDLE: SETTINGS + IMAGE ====================
        middle_layout = QHBoxLayout()
        middle_layout.setSpacing(10)
        outer_layout.addLayout(middle_layout, stretch=4)

        # LEFT: Settings panels
        settings_panel = QVBoxLayout()
        settings_panel.setSpacing(10)
        middle_layout.addLayout(settings_panel, stretch=1)

        # --- Camera Settings Panel ---
        cam_group = QGroupBox("Camera Settings")
        cam_group.setStyleSheet("QGroupBox { font-weight: bold; }")
        cam_layout = QGridLayout(cam_group)
        cam_layout.setSpacing(8)

        # Exposure row
        cam_layout.addWidget(QLabel("Exposure (ms):"), 0, 0)
        self.spin_exposure = QDoubleSpinBox()
        self.spin_exposure.setRange(1.0, 5000.0)
        self.spin_exposure.setValue(100.0)
        self.spin_exposure.setSingleStep(10.0)
        self.spin_exposure.setDecimals(1)
        self.spin_exposure.setMinimumWidth(80)
        cam_layout.addWidget(self.spin_exposure, 0, 1)
        self.btn_set_exposure = QPushButton("Set")
        self.btn_set_exposure.clicked.connect(self.on_set_exposure)
        cam_layout.addWidget(self.btn_set_exposure, 0, 2)

        # Gain row
        cam_layout.addWidget(QLabel("Gain (dB):"), 1, 0)
        self.spin_gain = QDoubleSpinBox()
        self.spin_gain.setRange(0.0, 48.0)
        self.spin_gain.setValue(0.0)
        self.spin_gain.setSingleStep(1.0)
        self.spin_gain.setDecimals(1)
        self.spin_gain.setMinimumWidth(80)
        cam_layout.addWidget(self.spin_gain, 1, 1)
        self.btn_set_gain = QPushButton("Set")
        self.btn_set_gain.clicked.connect(self.on_set_gain)
        cam_layout.addWidget(self.btn_set_gain, 1, 2)

        # White Balance preset row
        cam_layout.addWidget(QLabel("White Balance:"), 2, 0)
        self.combo_wb = QComboBox()
        self.combo_wb.addItems(["Default", "Warm", "Cool", "Reduce NIR", "Custom"])
        self.combo_wb.currentTextChanged.connect(self.on_wb_preset_changed)
        cam_layout.addWidget(self.combo_wb, 2, 1, 1, 2)

        # RGB on one row
        rgb_layout = QHBoxLayout()
        rgb_layout.setSpacing(4)
        rgb_layout.addWidget(QLabel("R:"))
        self.spin_wb_r = QDoubleSpinBox()
        self.spin_wb_r.setRange(0.1, 4.0)
        self.spin_wb_r.setValue(1.0)
        self.spin_wb_r.setSingleStep(0.1)
        self.spin_wb_r.setDecimals(2)
        self.spin_wb_r.setMaximumWidth(65)
        rgb_layout.addWidget(self.spin_wb_r)

        rgb_layout.addWidget(QLabel("G:"))
        self.spin_wb_g = QDoubleSpinBox()
        self.spin_wb_g.setRange(0.1, 4.0)
        self.spin_wb_g.setValue(1.0)
        self.spin_wb_g.setSingleStep(0.1)
        self.spin_wb_g.setDecimals(2)
        self.spin_wb_g.setMaximumWidth(65)
        rgb_layout.addWidget(self.spin_wb_g)

        rgb_layout.addWidget(QLabel("B:"))
        self.spin_wb_b = QDoubleSpinBox()
        self.spin_wb_b.setRange(0.1, 4.0)
        self.spin_wb_b.setValue(1.0)
        self.spin_wb_b.setSingleStep(0.1)
        self.spin_wb_b.setDecimals(2)
        self.spin_wb_b.setMaximumWidth(65)
        rgb_layout.addWidget(self.spin_wb_b)
        rgb_layout.addStretch()

        cam_layout.addLayout(rgb_layout, 3, 0, 1, 3)

        # Apply WB button
        self.btn_apply_wb = QPushButton("Apply White Balance")
        self.btn_apply_wb.clicked.connect(self.on_apply_white_balance)
        cam_layout.addWidget(self.btn_apply_wb, 4, 0, 1, 3)

        settings_panel.addWidget(cam_group)

        # --- Stage Control Panel ---
        stage_group = QGroupBox("Stage Control")
        stage_group.setStyleSheet("QGroupBox { font-weight: bold; }")
        stage_layout = QVBoxLayout(stage_group)
        stage_layout.setSpacing(10)

        # Current position display
        self.pos_label = QLabel("Position:  X = ?.??    Y = ?.??    Z = ?.??")
        self.pos_label.setStyleSheet("""
            QLabel {
                font-family: monospace;
                font-size: 12px;
                padding: 8px;
                background-color: #1a1a1a;
                border-radius: 4px;
            }
        """)
        stage_layout.addWidget(self.pos_label)

        # Step size + Refresh row
        step_layout = QHBoxLayout()
        step_layout.addWidget(QLabel("Step (mm):"))
        self.spin_step = QDoubleSpinBox()
        self.spin_step.setRange(0.1, 50.0)
        self.spin_step.setValue(5.0)
        self.spin_step.setSingleStep(1.0)
        self.spin_step.setDecimals(1)
        self.spin_step.setMaximumWidth(80)
        step_layout.addWidget(self.spin_step)
        step_layout.addStretch()
        self.btn_refresh_pos = QPushButton("↻ Refresh")
        self.btn_refresh_pos.clicked.connect(self.on_refresh_position)
        step_layout.addWidget(self.btn_refresh_pos)
        stage_layout.addLayout(step_layout)

        # Jog buttons - larger and clearer
        jog_grid = QGridLayout()
        jog_grid.setSpacing(6)

        jog_btn_style = """
            QPushButton {
                font-size: 16px;
                font-weight: bold;
                min-width: 50px;
                min-height: 35px;
            }
        """

        # X row
        x_label = QLabel("X:")
        x_label.setStyleSheet("font-weight: bold; font-size: 14px;")
        jog_grid.addWidget(x_label, 0, 0)
        self.btn_x_minus = QPushButton("−")
        self.btn_x_minus.setStyleSheet(jog_btn_style)
        self.btn_x_minus.clicked.connect(lambda: self.on_jog_axis(Axis.X, -1))
        jog_grid.addWidget(self.btn_x_minus, 0, 1)
        self.btn_x_plus = QPushButton("+")
        self.btn_x_plus.setStyleSheet(jog_btn_style)
        self.btn_x_plus.clicked.connect(lambda: self.on_jog_axis(Axis.X, 1))
        jog_grid.addWidget(self.btn_x_plus, 0, 2)

        # Y row
        y_label = QLabel("Y:")
        y_label.setStyleSheet("font-weight: bold; font-size: 14px;")
        jog_grid.addWidget(y_label, 1, 0)
        self.btn_y_minus = QPushButton("−")
        self.btn_y_minus.setStyleSheet(jog_btn_style)
        self.btn_y_minus.clicked.connect(lambda: self.on_jog_axis(Axis.Y, -1))
        jog_grid.addWidget(self.btn_y_minus, 1, 1)
        self.btn_y_plus = QPushButton("+")
        self.btn_y_plus.setStyleSheet(jog_btn_style)
        self.btn_y_plus.clicked.connect(lambda: self.on_jog_axis(Axis.Y, 1))
        jog_grid.addWidget(self.btn_y_plus, 1, 2)

        # Z row
        z_label = QLabel("Z:")
        z_label.setStyleSheet("font-weight: bold; font-size: 14px;")
        jog_grid.addWidget(z_label, 2, 0)
        self.btn_z_minus = QPushButton("−")
        self.btn_z_minus.setStyleSheet(jog_btn_style)
        self.btn_z_minus.clicked.connect(lambda: self.on_jog_axis(Axis.Z, -1))
        jog_grid.addWidget(self.btn_z_minus, 2, 1)
        self.btn_z_plus = QPushButton("+")
        self.btn_z_plus.setStyleSheet(jog_btn_style)
        self.btn_z_plus.clicked.connect(lambda: self.on_jog_axis(Axis.Z, 1))
        jog_grid.addWidget(self.btn_z_plus, 2, 2)

        # Add spacing column
        jog_grid.setColumnStretch(3, 1)

        stage_layout.addLayout(jog_grid)

        # Separator
        separator = QLabel("")
        separator.setStyleSheet("background-color: #3a3a3a; min-height: 1px; max-height: 1px;")
        stage_layout.addWidget(separator)

        # Absolute position entry - horizontal layout
        goto_layout = QHBoxLayout()
        goto_layout.setSpacing(8)

        goto_layout.addWidget(QLabel("Go to:"))

        goto_layout.addWidget(QLabel("X:"))
        self.spin_goto_x = QDoubleSpinBox()
        self.spin_goto_x.setRange(0.0, 300.0)
        self.spin_goto_x.setValue(200.0)
        self.spin_goto_x.setDecimals(2)
        self.spin_goto_x.setMaximumWidth(80)
        goto_layout.addWidget(self.spin_goto_x)

        goto_layout.addWidget(QLabel("Y:"))
        self.spin_goto_y = QDoubleSpinBox()
        self.spin_goto_y.setRange(0.0, 300.0)
        self.spin_goto_y.setValue(200.0)
        self.spin_goto_y.setDecimals(2)
        self.spin_goto_y.setMaximumWidth(80)
        goto_layout.addWidget(self.spin_goto_y)

        goto_layout.addWidget(QLabel("Z:"))
        self.spin_goto_z = QDoubleSpinBox()
        self.spin_goto_z.setRange(0.0, 300.0)
        self.spin_goto_z.setValue(200.0)
        self.spin_goto_z.setDecimals(2)
        self.spin_goto_z.setMaximumWidth(80)
        goto_layout.addWidget(self.spin_goto_z)

        self.btn_goto = QPushButton("Go")
        self.btn_goto.setStyleSheet("font-weight: bold; min-width: 60px;")
        self.btn_goto.clicked.connect(self.on_goto_position)
        goto_layout.addWidget(self.btn_goto)

        goto_layout.addStretch()
        stage_layout.addLayout(goto_layout)

        settings_panel.addWidget(stage_group)
        settings_panel.addStretch()

        # RIGHT: image display
        self.image_label = QLabel("Live / captured / processed image will appear here")
        self.image_label.setAlignment(Qt.AlignCenter)
        self.image_label.setStyleSheet("""
            QLabel {
                background-color: #1a1a1a;
                color: #666;
                border: 2px solid #333;
                border-radius: 8px;
                font-size: 14px;
            }
        """)
        self.image_label.setMinimumSize(800, 500)
        middle_layout.addWidget(self.image_label, stretch=2)

        # ==================== BOTTOM: LOG ====================
        log_group = QGroupBox("Log")
        log_group.setStyleSheet("QGroupBox { font-weight: bold; }")
        log_layout = QVBoxLayout(log_group)
        log_layout.setContentsMargins(4, 4, 4, 4)

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
        log_layout.addWidget(self.log_widget)
        outer_layout.addWidget(log_group)

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

    # ---------- status helper ----------

    def set_status(self, status: str, state: str = "disconnected"):
        """Update status label with colored indicator.

        Args:
            status: Text to display
            state: One of 'disconnected', 'connecting', 'ready', 'error'
        """
        colors = {
            "disconnected": "#ff6b6b",  # Red
            "connecting": "#ffd93d",     # Yellow
            "ready": "#6bcb77",          # Green
            "error": "#ff6b6b",          # Red
        }
        color = colors.get(state, "#ff6b6b")
        self.status_label.setText(f"● {status}")
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
            self.set_status("CONNECTING...", "connecting")
            self.log("Stage: connecting to all controllers...", "info")

            future = self.connection_service.connect()
            future.result(timeout=30)  # Wait for connection to complete

            self.set_status("CONNECTED", "connecting")
            self.log("Stage: all controllers connected successfully", "info")
        except Exception as e:
            self.set_status("ERROR", "error")
            self.log(f"Stage connect error: {e}", "error")
            QMessageBox.critical(self, "Connection error", str(e))

    def on_initialize_clicked(self):
        try:
            # Check if connected first
            if not self.connection_service.state.connection.name == "CONNECTED":
                QMessageBox.warning(self, "Not Connected",
                    "Please connect to controllers first.")
                return

            self.set_status("INITIALIZING...", "connecting")
            self.log("Stage: initializing and referencing all axes...", "info")

            # Wait for initialization to complete
            init_future = self.connection_service.initialize()
            init_future.result(timeout=120)  # Referencing can take time

            self.set_status("PARKING...", "connecting")
            self.log("Stage: initialization complete, moving to park position...", "info")

            # Now move to park position
            move_future = self.motion_service.move_to_position_safe_z(self.park_position)
            move_future.result(timeout=60)

            self.set_status("READY", "ready")
            self.log(f"Stage initialized and parked at {self.park_position}.", "info")
        except Exception as e:
            self.set_status("ERROR", "error")
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
