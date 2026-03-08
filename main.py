import os
import sys
from pathlib import Path

# Set up project root and paths FIRST
PROJECT_ROOT = Path(__file__).parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

# Add PI DLL directory to PATH before any PI imports
os.environ['PATH'] = str(PROJECT_ROOT) + os.pathsep + os.environ.get('PATH', '')

from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget,
    QHBoxLayout, QVBoxLayout, QPushButton, QLabel, QMessageBox, QTextEdit,
    QFileDialog, QGroupBox, QGridLayout, QDoubleSpinBox, QComboBox,
)
from PySide6.QtGui import QPixmap, QImage
from PySide6.QtCore import Qt, QTimer, QThread, Signal

# Hardware / vision imports
from device_drivers.PI_Control_System.core.models import Axis, Position
from device_drivers.PI_Control_System.app_factory import create_services
from device_drivers.thorlabs_camera_wrapper import ThorlabsCamera
from device_drivers.plate_auto_adjuster import auto_adjust_plate
from device_drivers.GPT_Merge import analyze_plate_and_spots
from device_drivers.spot_analysis.pipeline import run_spot_analysis
from device_drivers.image_utils import load_image, save_image, bgr_to_rgb


# ---------------------------------------------------------------------------
# Background worker – keeps WE Detect off the UI thread
# ---------------------------------------------------------------------------

class SpotAnalysisWorker(QThread):
    """Run run_spot_analysis() in a background thread.

    Signals:
        finished(dict)  – emitted with the full result dict on success
        error(str)      – emitted with an error message on failure
    """
    finished = Signal(dict)
    error = Signal(str)

    def __init__(self, image_path: str, output_dir: str) -> None:
        super().__init__()
        self.image_path = image_path
        self.output_dir = output_dir

    def run(self) -> None:
        try:
            result = run_spot_analysis(
                image_path=self.image_path,
                output_dir=self.output_dir,
                export_excel=True,
            )
            self.finished.emit(result)
        except Exception as exc:
            self.error.emit(str(exc))


# ---------------------------------------------------------------------------
# Main application window
# ---------------------------------------------------------------------------

class SimpleStageApp(QMainWindow):
    def __init__(self, use_mock: bool = True):
        super().__init__()

        # --- PI services ---
        event_bus, connection_service, motion_service, config = create_services(use_mock=use_mock)
        self.event_bus = event_bus
        self.connection_service = connection_service
        self.motion_service = motion_service

        # --- Camera ---
        TL_DLL_DIR = r"C:\Program Files\Thorlabs\ThorImageCAM\Bin"
        self.camera = ThorlabsCamera(dll_dir=TL_DLL_DIR)
        self.live_timer = QTimer(self)
        self.live_timer.timeout.connect(self._update_live_view)
        self.live_running = False

        # --- State ---
        self.last_image_path: str | None = None
        self.last_plate_path: str | None = None
        self._we_worker: SpotAnalysisWorker | None = None

        # --- Positions ---
        self.park_position = Position(x=200.0, y=200.0, z=200.0)

        # ================================================================
        # Window layout
        # ================================================================
        self.setWindowTitle("CTA – Stage + Plate Check")
        self.resize(1400, 850)

        central = QWidget()
        outer_layout = QVBoxLayout(central)
        outer_layout.setContentsMargins(8, 8, 8, 8)
        outer_layout.setSpacing(8)
        self.setCentralWidget(central)

        # ---- Top toolbar ----
        toolbar_layout = QHBoxLayout()
        toolbar_layout.setSpacing(6)

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

        btn_style = """
            QPushButton {
                padding: 8px 16px;
                font-weight: bold;
                border-radius: 4px;
                min-width: 80px;
            }
            QPushButton:hover  { background-color: #4a4a4a; }
            QPushButton:pressed { background-color: #3a3a3a; }
        """

        self.btn_connect  = QPushButton("Connect")
        self.btn_init     = QPushButton("Initialize")
        self.btn_cam_start = QPushButton("Camera")
        self.btn_capture  = QPushButton("Capture")
        self.btn_plate    = QPushButton("Plate Detect")
        self.btn_adjust   = QPushButton("Auto Adjust")
        self.btn_we       = QPushButton("WE Detect")

        for btn in [self.btn_connect, self.btn_init, self.btn_cam_start,
                    self.btn_capture, self.btn_plate, self.btn_adjust, self.btn_we]:
            btn.setStyleSheet(btn_style)
            toolbar_layout.addWidget(btn)

        toolbar_layout.addStretch()
        outer_layout.addLayout(toolbar_layout)

        # ---- Middle: settings + image ----
        middle_layout = QHBoxLayout()
        middle_layout.setSpacing(10)
        outer_layout.addLayout(middle_layout, stretch=4)

        settings_panel = QVBoxLayout()
        settings_panel.setSpacing(10)
        middle_layout.addLayout(settings_panel, stretch=1)

        # Camera settings group
        cam_group = QGroupBox("Camera Settings")
        cam_group.setStyleSheet("QGroupBox { font-weight: bold; }")
        cam_layout = QGridLayout(cam_group)
        cam_layout.setSpacing(8)

        cam_layout.addWidget(QLabel("Exposure (ms):"), 0, 0)
        self.spin_exposure = QDoubleSpinBox()
        self.spin_exposure.setRange(1.0, 5000.0)
        self.spin_exposure.setValue(100.0)
        self.spin_exposure.setSingleStep(10.0)
        self.spin_exposure.setDecimals(1)
        self.spin_exposure.setMinimumWidth(80)
        cam_layout.addWidget(self.spin_exposure, 0, 1)
        btn_exp = QPushButton("Set")
        btn_exp.clicked.connect(self.on_set_exposure)
        cam_layout.addWidget(btn_exp, 0, 2)

        cam_layout.addWidget(QLabel("Gain (dB):"), 1, 0)
        self.spin_gain = QDoubleSpinBox()
        self.spin_gain.setRange(0.0, 48.0)
        self.spin_gain.setValue(0.0)
        self.spin_gain.setSingleStep(1.0)
        self.spin_gain.setDecimals(1)
        self.spin_gain.setMinimumWidth(80)
        cam_layout.addWidget(self.spin_gain, 1, 1)
        btn_gain = QPushButton("Set")
        btn_gain.clicked.connect(self.on_set_gain)
        cam_layout.addWidget(btn_gain, 1, 2)

        cam_layout.addWidget(QLabel("White Balance:"), 2, 0)
        self.combo_wb = QComboBox()
        self.combo_wb.addItems(["Default", "Warm", "Cool", "Reduce NIR", "Custom"])
        self.combo_wb.currentTextChanged.connect(self.on_wb_preset_changed)
        cam_layout.addWidget(self.combo_wb, 2, 1, 1, 2)

        rgb_layout = QHBoxLayout()
        rgb_layout.setSpacing(4)
        for label_text, attr in [("R:", "spin_wb_r"), ("G:", "spin_wb_g"), ("B:", "spin_wb_b")]:
            rgb_layout.addWidget(QLabel(label_text))
            spin = QDoubleSpinBox()
            spin.setRange(0.1, 4.0)
            spin.setValue(1.0)
            spin.setSingleStep(0.1)
            spin.setDecimals(2)
            spin.setMaximumWidth(65)
            setattr(self, attr, spin)
            rgb_layout.addWidget(spin)
        rgb_layout.addStretch()
        cam_layout.addLayout(rgb_layout, 3, 0, 1, 3)

        self.btn_apply_wb = QPushButton("Apply White Balance")
        self.btn_apply_wb.clicked.connect(self.on_apply_white_balance)
        cam_layout.addWidget(self.btn_apply_wb, 4, 0, 1, 3)

        settings_panel.addWidget(cam_group)

        # Stage control group
        stage_group = QGroupBox("Stage Control")
        stage_group.setStyleSheet("QGroupBox { font-weight: bold; }")
        stage_layout = QVBoxLayout(stage_group)
        stage_layout.setSpacing(10)

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
        btn_refresh = QPushButton("↻ Refresh")
        btn_refresh.clicked.connect(self.on_refresh_position)
        step_layout.addWidget(btn_refresh)
        stage_layout.addLayout(step_layout)

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
        for row_idx, (axis, label) in enumerate([(Axis.X, "X"), (Axis.Y, "Y"), (Axis.Z, "Z")]):
            lbl = QLabel(f"{label}:")
            lbl.setStyleSheet("font-weight: bold; font-size: 14px;")
            jog_grid.addWidget(lbl, row_idx, 0)
            for col_idx, direction in enumerate([-1, 1]):
                symbol = "−" if direction == -1 else "+"
                btn = QPushButton(symbol)
                btn.setStyleSheet(jog_btn_style)
                btn.clicked.connect(lambda checked=False, a=axis, d=direction: self.on_jog_axis(a, d))
                jog_grid.addWidget(btn, row_idx, col_idx + 1)
        jog_grid.setColumnStretch(3, 1)
        stage_layout.addLayout(jog_grid)

        separator = QLabel("")
        separator.setStyleSheet("background-color: #3a3a3a; min-height: 1px; max-height: 1px;")
        stage_layout.addWidget(separator)

        goto_layout = QHBoxLayout()
        goto_layout.setSpacing(8)
        goto_layout.addWidget(QLabel("Go to:"))
        self.spin_goto_x = QDoubleSpinBox()
        self.spin_goto_y = QDoubleSpinBox()
        self.spin_goto_z = QDoubleSpinBox()
        for axis_lbl, spin in [("X:", self.spin_goto_x), ("Y:", self.spin_goto_y), ("Z:", self.spin_goto_z)]:
            spin.setRange(0.0, 300.0)
            spin.setValue(200.0)
            spin.setDecimals(2)
            spin.setMaximumWidth(80)
            goto_layout.addWidget(QLabel(axis_lbl))
            goto_layout.addWidget(spin)
        btn_goto = QPushButton("Go")
        btn_goto.setStyleSheet("font-weight: bold; min-width: 60px;")
        btn_goto.clicked.connect(self.on_goto_position)
        goto_layout.addWidget(btn_goto)
        goto_layout.addStretch()
        stage_layout.addLayout(goto_layout)

        settings_panel.addWidget(stage_group)
        settings_panel.addStretch()

        # Image display
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

        # ---- Log panel ----
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

        # ---- Wire buttons ----
        self.btn_connect.clicked.connect(self.on_connect_clicked)
        self.btn_init.clicked.connect(self.on_initialize_clicked)
        self.btn_cam_start.clicked.connect(self.on_cam_start_clicked)
        self.btn_capture.clicked.connect(self.on_capture_clicked)
        self.btn_plate.clicked.connect(self.on_plate_clicked)
        self.btn_adjust.clicked.connect(self.on_adjust_clicked)
        self.btn_we.clicked.connect(self.on_we_clicked)

    # ================================================================
    # Helpers
    # ================================================================

    def log(self, message: str, level: str = "info") -> None:
        prefix = {"info": "[INFO]", "warn": "[WARN]", "error": "[ERROR]"}.get(level, "[INFO]")
        self.log_widget.append(f"{prefix} {message}")

    def set_status(self, status: str, state: str = "disconnected") -> None:
        colors = {
            "disconnected": "#ff6b6b",
            "connecting":   "#ffd93d",
            "ready":        "#6bcb77",
            "error":        "#ff6b6b",
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

    def _show_image(self, img) -> None:
        """Display a BGR ndarray in the image panel."""
        img_rgb = bgr_to_rgb(img)
        h, w, ch = img_rgb.shape
        qimg = QImage(img_rgb.data, w, h, ch * w, QImage.Format_RGB888)
        pix = QPixmap.fromImage(qimg).scaled(
            self.image_label.width(),
            self.image_label.height(),
            Qt.KeepAspectRatio,
            Qt.SmoothTransformation,
        )
        self.image_label.setPixmap(pix)

    def _is_stage_ready(self) -> bool:
        return self.connection_service.is_ready()

    def _pick_image_file(self, title: str) -> str | None:
        path, _ = QFileDialog.getOpenFileName(
            self, title, str(PROJECT_ROOT),
            "Images (*.png *.jpg *.jpeg *.bmp)",
        )
        return path or None

    # ================================================================
    # Workflow button handlers
    # ================================================================

    def on_connect_clicked(self) -> None:
        try:
            self.set_status("CONNECTING...", "connecting")
            self.log("Stage: connecting to all controllers...", "info")
            self.connection_service.connect().result(timeout=30)
            self.set_status("CONNECTED", "connecting")
            self.log("Stage: all controllers connected successfully.", "info")
        except Exception as exc:
            self.set_status("ERROR", "error")
            self.log(f"Stage connect error: {exc}", "error")
            QMessageBox.critical(self, "Connection error", str(exc))

    def on_initialize_clicked(self) -> None:
        try:
            if not self.connection_service.state.connection.name == "CONNECTED":
                QMessageBox.warning(self, "Not Connected",
                    "Please connect to controllers first.")
                return

            self.set_status("INITIALIZING...", "connecting")
            self.log("Stage: initializing and referencing all axes...", "info")
            self.connection_service.initialize().result(timeout=120)

            self.set_status("PARKING...", "connecting")
            self.log("Stage: moving to park position...", "info")
            self.motion_service.move_to_position_safe_z(self.park_position).result(timeout=60)

            self.set_status("READY", "ready")
            self.log(f"Stage initialized and parked at {self.park_position}.", "info")
        except Exception as exc:
            self.set_status("ERROR", "error")
            self.log(f"Initialize error: {exc}", "error")
            QMessageBox.critical(self, "Initialize error", str(exc))

    def on_cam_start_clicked(self) -> None:
        if not self.live_running:
            try:
                if not self.camera.is_connected:
                    self.camera.connect()
                self.live_timer.start(100)
                self.live_running = True
                self.btn_cam_start.setText("Camera Stop (live)")
                self.log("Camera live view started.", "info")
            except Exception as exc:
                self.log(f"Live start error: {exc}", "error")
        else:
            self.live_timer.stop()
            self.live_running = False
            self.btn_cam_start.setText("Camera")
            self.log("Camera live view stopped.", "info")

    def on_capture_clicked(self) -> None:
        """Capture a frame from the camera, or load a file if no camera."""
        camera_available = self.camera.is_connected
        if not camera_available:
            try:
                self.camera.connect()
                camera_available = True
            except Exception:
                camera_available = False

        if camera_available:
            self._capture_from_camera()
        else:
            self._capture_from_file()

    def _capture_from_camera(self) -> None:
        try:
            save_dir = PROJECT_ROOT / "artifacts" / "captures"
            save_dir.mkdir(parents=True, exist_ok=True)

            exp  = self.spin_exposure.value()
            gain = self.spin_gain.value()
            r, g, b = self.spin_wb_r.value(), self.spin_wb_g.value(), self.spin_wb_b.value()

            base = f"Photo_{exp:.1f}_{gain:.1f}_{r:.2f}_{g:.2f}_{b:.2f}"
            filename = save_dir / f"{base}.png"
            counter = 1
            while filename.exists():
                filename = save_dir / f"{base}_{counter}.png"
                counter += 1

            frame = self.camera.save_frame(str(filename))
            self.last_image_path = str(filename)
            self._show_image(frame)
            self.log(f"Captured: {filename}", "info")
        except Exception as exc:
            self.log(f"Capture error: {exc}", "error")
            QMessageBox.critical(self, "Capture error", str(exc))

    def _capture_from_file(self) -> None:
        self.log("Camera not connected – select an image file.", "warn")
        path = self._pick_image_file("Select image (no camera connected)")
        if not path:
            self.log("Capture cancelled.", "warn")
            return
        img = load_image(path)
        if img is None:
            self.log(f"Could not load image: {path}", "error")
            QMessageBox.critical(self, "Load error", f"Cannot read image:\n{path}")
            return
        self.last_image_path = path
        self._show_image(img)
        self.log(f"Loaded image from file: {path}", "info")

    def on_plate_clicked(self) -> None:
        """Detect the plate in the last captured image."""
        image_path = self.last_image_path
        if not image_path:
            image_path = self._pick_image_file("Select image for plate detection")
            if not image_path:
                self.log("Plate detection cancelled.", "warn")
                return
            self.log(f"Using user-selected image: {image_path}", "info")

        try:
            save_dir = PROJECT_ROOT / "artifacts" / "plate_detection"
            save_dir.mkdir(parents=True, exist_ok=True)

            result = analyze_plate_and_spots(image_path, str(save_dir))

            if result.get("error"):
                msg = f"Detection error: {result['error']}"
                self.log(msg, "warn")
                QMessageBox.warning(self, "Plate detection", msg)
                return

            if not result["plate_detected"]:
                msg = "No plate detected in image."
                self.log(msg, "warn")
                QMessageBox.warning(self, "Plate detection", msg)
                return

            plate_img  = result["plate_image"]
            plate_path = str(save_dir / "plate.png")
            save_image(plate_path, plate_img)
            self.last_plate_path = plate_path

            self._show_image(plate_img)
            bbox = result["plate_bbox"]
            self.log(f"Plate detected at {bbox}. Saved to: {plate_path}", "info")
            QMessageBox.information(self, "Plate detection",
                f"Plate detected at {bbox}\nSaved to: {plate_path}")
        except Exception as exc:
            self.log(f"Plate detection error: {exc}", "error")
            QMessageBox.critical(self, "Plate detection error", str(exc))

    def on_adjust_clicked(self) -> None:
        """Run the closed-loop auto-adjust feedback loop."""
        if not self._is_stage_ready():
            QMessageBox.warning(self, "Stage Not Ready",
                "Please connect and initialize the stage first.")
            return
        try:
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
                self.log(line, "info")

            if fully:
                self.log(f"Auto-adjust succeeded. hint={final_hint}", "info")
                QMessageBox.information(self, "Auto Adjust",
                    f"Plate centred successfully. hint={final_hint}")
            else:
                self.log(f"Auto-adjust did not fully succeed. hint={final_hint}", "warn")
                QMessageBox.warning(self, "Auto Adjust",
                    f"Could not fully centre plate. hint={final_hint}")
        except Exception as exc:
            self.log(f"Auto adjust error: {exc}", "error")
            QMessageBox.critical(self, "Auto Adjust error", str(exc))

    def on_we_clicked(self) -> None:
        """Start the WE spot analysis pipeline in a background thread."""
        image_path = self.last_plate_path

        if not image_path:
            self.log("No plate detected yet. Select an image manually?", "warn")
            reply = QMessageBox.question(
                self, "WE Detection",
                "No plate image available.\n\nSelect an image manually?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            )
            if reply != QMessageBox.StandardButton.Yes:
                return
            image_path = self._pick_image_file("Select image for WE detection")
            if not image_path:
                self.log("WE detection cancelled.", "warn")
                return
            self.log(f"WE detection using: {image_path}", "info")
        else:
            self.log(f"WE detection using plate image: {image_path}", "info")

        save_dir = str(PROJECT_ROOT / "artifacts" / "we_detection")

        self.btn_we.setEnabled(False)
        self.btn_we.setText("WE Detect (running…)")

        self._we_worker = SpotAnalysisWorker(image_path, save_dir)
        self._we_worker.finished.connect(self._on_we_finished)
        self._we_worker.error.connect(self._on_we_error)
        self._we_worker.start()

    def _on_we_finished(self, result: dict) -> None:
        """Called on the UI thread when SpotAnalysisWorker completes."""
        self.btn_we.setEnabled(True)
        self.btn_we.setText("WE Detect")

        overlay = result.get("overlay_image")
        if overlay is not None:
            self._show_image(overlay)

        total    = len(result["all_spots"])
        accepted = len(result["accepted_spots"])
        rejected = len(result["rejected_spots"])
        rejected_labels = result.get("rejected_labels", [])
        missing_spots   = result.get("missing_spots", [])
        excel_path      = result.get("excel_path")
        non_fatal_error = result.get("error")

        self.log(f"Detected spots:  {total}", "info")
        self.log(f"Accepted:        {accepted}", "info")
        self.log(f"Rejected:        {rejected}", "warn" if rejected else "info")

        if rejected_labels:
            self.log(f"Rejected labels: {', '.join(rejected_labels)}", "warn")
        if missing_spots:
            self.log(f"Missing spots:   {', '.join(missing_spots)}", "warn")
        if excel_path:
            self.log(f"Excel saved:     {excel_path}", "info")
        if non_fatal_error:
            self.log(f"Warning: {non_fatal_error}", "warn")

        issues: list[str] = []
        if rejected:
            issues.append(f"Rejected: {rejected} spot(s) – {', '.join(rejected_labels)}")
        if missing_spots:
            issues.append(f"Missing: {', '.join(missing_spots)}")

        if not issues:
            QMessageBox.information(self, "WE Detection",
                f"All {accepted} spot(s) accepted.\nNo defects detected.")
        else:
            QMessageBox.warning(self, "WE Detection",
                f"Detected: {total}  |  Accepted: {accepted}  |  Rejected: {rejected}\n"
                + "\n".join(issues))

    def _on_we_error(self, error_msg: str) -> None:
        self.btn_we.setEnabled(True)
        self.btn_we.setText("WE Detect")
        self.log(f"WE detection error: {error_msg}", "error")
        QMessageBox.critical(self, "WE Detection Error", error_msg)

    # ================================================================
    # Camera settings handlers
    # ================================================================

    def on_set_exposure(self) -> None:
        if not self.camera.is_connected:
            self.log("Camera not connected.", "warn")
            return
        try:
            ms = self.spin_exposure.value()
            self.camera.set_exposure(ms / 1000.0)
            self.log(f"Exposure set to {ms:.1f} ms.", "info")
        except Exception as exc:
            self.log(f"Set exposure error: {exc}", "error")

    def on_set_gain(self) -> None:
        if not self.camera.is_connected:
            self.log("Camera not connected.", "warn")
            return
        try:
            gain = self.spin_gain.value()
            self.camera.set_gain(gain)
            self.log(f"Gain set to {gain:.1f} dB.", "info")
        except Exception as exc:
            self.log(f"Set gain error: {exc}", "error")

    def on_wb_preset_changed(self, preset: str) -> None:
        presets = {
            "Default":     (1.0, 1.0, 1.0),
            "Warm":        (1.0, 0.9, 0.7),
            "Cool":        (0.9, 1.0, 1.2),
            "Reduce NIR":  (0.6, 0.8, 1.0),
        }
        if preset in presets:
            r, g, b = presets[preset]
            self.spin_wb_r.setValue(r)
            self.spin_wb_g.setValue(g)
            self.spin_wb_b.setValue(b)
            self.on_apply_white_balance()

    def on_apply_white_balance(self) -> None:
        try:
            r, g, b = self.spin_wb_r.value(), self.spin_wb_g.value(), self.spin_wb_b.value()
            self.camera.set_white_balance(r, g, b)
            self.log(f"White balance: R={r:.2f} G={g:.2f} B={b:.2f}", "info")
        except Exception as exc:
            self.log(f"Set white balance error: {exc}", "error")

    # ================================================================
    # Stage control handlers
    # ================================================================

    def on_refresh_position(self) -> None:
        if not self._is_stage_ready():
            self.log("Cannot get position: stage not initialized.", "warn")
            return
        try:
            pos = self.motion_service.get_current_position()
            self.pos_label.setText(f"Position: X={pos.x:.2f}  Y={pos.y:.2f}  Z={pos.z:.2f}")
            self.spin_goto_x.setValue(pos.x)
            self.spin_goto_y.setValue(pos.y)
            self.spin_goto_z.setValue(pos.z)
            self.log(f"Position: X={pos.x:.2f} Y={pos.y:.2f} Z={pos.z:.2f}", "info")
        except Exception as exc:
            self.log(f"Get position error: {exc}", "error")

    def on_jog_axis(self, axis: Axis, direction: int) -> None:
        if not self._is_stage_ready():
            QMessageBox.warning(self, "Stage Not Ready",
                "Please connect and initialize the stage first.")
            return
        try:
            step = self.spin_step.value() * direction
            self.log(f"Jogging {axis.value} by {step:+.1f} mm…", "info")
            self.motion_service.move_axis_relative(axis, step).result(timeout=30)
            self.on_refresh_position()
        except Exception as exc:
            self.log(f"Jog {axis.value} error: {exc}", "error")

    def on_goto_position(self) -> None:
        if not self._is_stage_ready():
            QMessageBox.warning(self, "Stage Not Ready",
                "Please connect and initialize the stage first.")
            return
        try:
            target = Position(
                x=self.spin_goto_x.value(),
                y=self.spin_goto_y.value(),
                z=self.spin_goto_z.value(),
            )
            self.log(f"Moving to X={target.x:.2f} Y={target.y:.2f} Z={target.z:.2f}…", "info")
            self.motion_service.move_to_position_safe_z(target).result(timeout=60)
            self.on_refresh_position()
            self.log("Move complete.", "info")
        except Exception as exc:
            self.log(f"Go to position error: {exc}", "error")

    # ================================================================
    # Live view
    # ================================================================

    def _update_live_view(self) -> None:
        try:
            frame = self.camera.grab_frame()
            self._show_image(frame)
        except Exception as exc:
            self.log(f"Live view error: {exc}", "error")
            self.live_timer.stop()
            self.live_running = False
            self.btn_cam_start.setText("Camera")

    # ================================================================
    # Shutdown
    # ================================================================

    def closeEvent(self, event) -> None:
        self.log("Closing – disconnecting hardware…", "info")

        if self.live_running:
            self.live_timer.stop()
            self.live_running = False

        if self._we_worker and self._we_worker.isRunning():
            self._we_worker.quit()
            self._we_worker.wait(3000)

        try:
            if self.camera.is_connected:
                self.camera.disconnect()
        except Exception as exc:
            print(f"Camera disconnect error: {exc}")

        try:
            self.connection_service.shutdown()
        except Exception as exc:
            print(f"Stage disconnect error: {exc}")

        event.accept()


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main() -> None:
    app = QApplication(sys.argv)
    window = SimpleStageApp(use_mock=False)
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
