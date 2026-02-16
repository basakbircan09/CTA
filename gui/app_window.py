import cv2
from pathlib import Path

from PySide6.QtWidgets import (
    QMainWindow, QWidget, QHBoxLayout, QVBoxLayout,
    QMessageBox, QFileDialog,
)
from PySide6.QtCore import QTimer

from device_drivers.PI_Control_System.app_factory import create_services
from device_drivers.PI_Control_System.core.models import Axis, Position
from device_drivers.thorlabs_camera_wrapper import ThorlabsCamera
from device_drivers.plate_auto_adjuster import auto_adjust_plate
from device_drivers.GPT_Merge import analyze_plate_and_spots
from config.app_config_loader import load_app_config

from gui.widgets.toolbar import WorkflowToolbar
from gui.widgets.camera_settings import CameraSettingsPanel
from gui.widgets.stage_control import StageControlPanel
from gui.widgets.image_viewer import ImageViewer
from gui.widgets.log_panel import LogPanel

PROJECT_ROOT = Path(__file__).resolve().parent.parent


class SimpleStageApp(QMainWindow):
    def __init__(self, use_mock: bool = True):
        super().__init__()

        # --- Load config ---
        self.config = load_app_config()

        # --- PI services ---
        event_bus, connection_service, motion_service, _pi_cfg = create_services(
            use_mock=use_mock
        )
        self.event_bus = event_bus
        self.connection_service = connection_service
        self.motion_service = motion_service

        # --- Thorlabs camera ---
        tl_dll_dir = self.config.get("thorlabs", {}).get(
            "dll_dir", r"C:\Program Files\Thorlabs\ThorImageCAM\Bin"
        )
        self.camera = ThorlabsCamera(dll_dir=tl_dll_dir)
        self.live_timer = QTimer(self)
        self.live_timer.timeout.connect(self._update_live_view)
        self.live_running = False

        # State
        self.last_image_path: str | None = None
        self.last_plate_path: str | None = None
        self.park_position = Position(x=200.0, y=200.0, z=200.0)
        self.default_position = Position(x=150.0, y=150.0, z=150.0)

        # --- Build UI ---
        self.setWindowTitle("CTA – Stage + Plate Check")
        self.resize(1400, 850)

        central = QWidget()
        outer_layout = QVBoxLayout(central)
        outer_layout.setContentsMargins(8, 8, 8, 8)
        outer_layout.setSpacing(8)
        self.setCentralWidget(central)

        # Top toolbar
        self.toolbar = WorkflowToolbar()
        outer_layout.addWidget(self.toolbar)

        # Middle: settings + image
        middle_layout = QHBoxLayout()
        middle_layout.setSpacing(10)
        outer_layout.addLayout(middle_layout, stretch=4)

        # Left: settings panels
        settings_panel = QVBoxLayout()
        settings_panel.setSpacing(10)
        middle_layout.addLayout(settings_panel, stretch=1)

        self.camera_settings = CameraSettingsPanel()
        settings_panel.addWidget(self.camera_settings)

        self.stage_control = StageControlPanel()
        settings_panel.addWidget(self.stage_control)
        settings_panel.addStretch()

        # Right: image display
        self.image_viewer = ImageViewer()
        middle_layout.addWidget(self.image_viewer, stretch=2)

        # Bottom: log
        self.log_panel = LogPanel()
        outer_layout.addWidget(self.log_panel)

        # Wire signals
        self._wire_signals()

    # ---------- signal wiring ----------

    def _wire_signals(self):
        # Toolbar
        self.toolbar.connect_clicked.connect(self.on_connect_clicked)
        self.toolbar.initialize_clicked.connect(self.on_initialize_clicked)
        self.toolbar.camera_toggled.connect(self.on_cam_start_clicked)
        self.toolbar.capture_clicked.connect(self.on_capture_clicked)
        self.toolbar.plate_detect_clicked.connect(self.on_plate_clicked)
        self.toolbar.auto_adjust_clicked.connect(self.on_adjust_clicked)
        self.toolbar.we_detect_clicked.connect(self.on_we_clicked)

        # Camera settings
        self.camera_settings.exposure_changed.connect(self._apply_exposure)
        self.camera_settings.gain_changed.connect(self._apply_gain)
        self.camera_settings.white_balance_changed.connect(self._apply_white_balance)

        # Stage control
        self.stage_control.jog_requested.connect(self.on_jog_axis)
        self.stage_control.goto_requested.connect(self.on_goto_position)
        self.stage_control.refresh_requested.connect(self.on_refresh_position)

    # ---------- logging / status helpers ----------

    def log(self, message: str, level: str = "info"):
        self.log_panel.log(message, level)

    def set_status(self, text: str, state: str = "disconnected"):
        self.toolbar.set_status(text, state)

    # ---------- camera settings handlers ----------

    def _apply_exposure(self, exposure_sec: float):
        try:
            if not self.camera.is_connected:
                self.log("Camera not connected", "warn")
                return
            self.camera.set_exposure(exposure_sec)
            self.log(f"Exposure set to {exposure_sec * 1000:.1f} ms", "info")
        except Exception as e:
            self.log(f"Set exposure error: {e}", "error")

    def _apply_gain(self, gain: float):
        try:
            if not self.camera.is_connected:
                self.log("Camera not connected", "warn")
                return
            self.camera.set_gain(gain)
            self.log(f"Gain set to {gain:.1f}", "info")
        except Exception as e:
            self.log(f"Set gain error: {e}", "error")

    def _apply_white_balance(self, r: float, g: float, b: float):
        try:
            self.camera.set_white_balance(r, g, b)
            self.log(f"White balance set to R={r:.2f} G={g:.2f} B={b:.2f}", "info")
        except Exception as e:
            self.log(f"Set white balance error: {e}", "error")

    # ---------- workflow handlers ----------

    def on_connect_clicked(self):
        try:
            self.set_status("CONNECTING...", "connecting")
            self.log("Stage: connecting to all controllers...", "info")

            future = self.connection_service.connect()
            future.result(timeout=30)

            self.set_status("CONNECTED", "connecting")
            self.log("Stage: all controllers connected successfully", "info")
        except Exception as e:
            self.set_status("ERROR", "error")
            self.log(f"Stage connect error: {e}", "error")
            QMessageBox.critical(self, "Connection error", str(e))

    def on_initialize_clicked(self):
        try:
            if not self.connection_service.state.connection.name == "CONNECTED":
                QMessageBox.warning(self, "Not Connected",
                    "Please connect to controllers first.")
                return

            self.set_status("INITIALIZING...", "connecting")
            self.log("Stage: initializing and referencing all axes...", "info")

            init_future = self.connection_service.initialize()
            init_future.result(timeout=120)

            self.set_status("PARKING...", "connecting")
            self.log("Stage: initialization complete, moving to park position...", "info")

            move_future = self.motion_service.move_to_position_safe_z(self.park_position)
            move_future.result(timeout=60)

            self.set_status("READY", "ready")
            self.log(f"Stage initialized and parked at {self.park_position}.", "info")
        except Exception as e:
            self.set_status("ERROR", "error")
            self.log(f"Initialize error: {e}", "error")
            QMessageBox.critical(self, "Initialize error", str(e))

    def on_cam_start_clicked(self):
        if not self.live_running:
            try:
                if not self.camera.is_connected:
                    self.camera.connect()
                self.live_timer.start(100)
                self.live_running = True
                self.toolbar.btn_cam_start.setText("Camera Stop")
                self.log("Camera live started", "info")
            except Exception as e:
                self.log(f"Live start error: {e}", "error")
        else:
            self.live_timer.stop()
            self.live_running = False
            self.toolbar.btn_cam_start.setText("Camera")
            self.log("Camera live stopped", "info")

    def on_capture_clicked(self):
        try:
            if not self.camera.is_connected:
                self.camera.connect()

            save_dir = PROJECT_ROOT / "artifacts" / "captures"
            save_dir.mkdir(parents=True, exist_ok=True)

            exp = self.camera_settings.spin_exposure.value()
            gain = self.camera_settings.spin_gain.value()
            r = self.camera_settings.spin_wb_r.value()
            g = self.camera_settings.spin_wb_g.value()
            b = self.camera_settings.spin_wb_b.value()

            base_name = f"Photo_{exp:.1f}_{gain:.1f}_{r:.2f}_{g:.2f}_{b:.2f}"

            filename = save_dir / f"{base_name}.png"
            counter = 1
            while filename.exists():
                filename = save_dir / f"{base_name}_{counter}.png"
                counter += 1

            frame = self.camera.save_frame(str(filename))
            self.last_image_path = str(filename)

            self.image_viewer.show_cv_image(frame)
            self.log(f"Captured image: {filename}", "info")
        except Exception as e:
            self.log(f"Capture error: {e}", "error")
            QMessageBox.critical(self, "Capture error", str(e))

    def on_plate_clicked(self):
        image_path = self.last_image_path

        if not image_path:
            file_path, _ = QFileDialog.getOpenFileName(
                self, "Select image for plate detection",
                str(PROJECT_ROOT), "Images (*.png *.jpg *.jpeg *.bmp)",
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

            plate_img = result["plate_image"]
            plate_path = save_dir / "plate.png"
            cv2.imwrite(str(plate_path), plate_img)
            self.last_plate_path = str(plate_path)

            self.image_viewer.show_cv_image(plate_img)

            bbox = result["plate_bbox"]
            msg = f"Plate detected at {bbox}\nSaved to: {plate_path}"
            self.log(msg, "info")
            QMessageBox.information(self, "Plate detection", msg)
        except Exception as e:
            self.log(f"Plate detection error: {e}", "error")
            QMessageBox.critical(self, "Plate detection error", str(e))

    def on_adjust_clicked(self):
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
        image_path = self.last_plate_path

        if not image_path:
            msg = "No plate detected yet. Please run Plate Detection first, or select an image manually."
            self.log(msg, "warn")
            reply = QMessageBox.question(
                self, "WE Detection",
                msg + "\n\nWould you like to select an image manually?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            )
            if reply == QMessageBox.StandardButton.Yes:
                file_path, _ = QFileDialog.getOpenFileName(
                    self, "Select image for WE (bubble) detection",
                    str(PROJECT_ROOT), "Images (*.png *.jpg *.jpeg *.bmp)",
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

            output_img = result["accepted_spots_image"]
            if output_img is not None:
                self.image_viewer.show_cv_image(output_img)

            accepted = len(result["accepted_spots"])
            rejected = len(result["rejected_spots"])
            total = len(result["all_spots"])

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

    # ---------- stage control handlers ----------

    def _is_stage_ready(self) -> bool:
        return self.connection_service.is_ready()

    def on_refresh_position(self):
        if not self._is_stage_ready():
            self.log("Cannot get position: stage not initialized", "warn")
            return
        try:
            pos = self.motion_service.get_current_position()
            self.stage_control.update_position(pos)
            self.log(f"Position: X={pos.x:.2f} Y={pos.y:.2f} Z={pos.z:.2f}", "info")
        except Exception as e:
            self.log(f"Get position error: {e}", "error")

    def on_jog_axis(self, axis: Axis, step: float):
        if not self._is_stage_ready():
            QMessageBox.warning(self, "Stage Not Ready",
                "Please connect and initialize the stage first.")
            return
        try:
            self.log(f"Jogging {axis.value} by {step:+.1f} mm...", "info")
            future = self.motion_service.move_axis_relative(axis, step)
            future.result(timeout=30)
            self.on_refresh_position()
        except Exception as e:
            self.log(f"Jog {axis.value} error: {e}", "error")

    def on_goto_position(self, target: Position):
        if not self._is_stage_ready():
            QMessageBox.warning(self, "Stage Not Ready",
                "Please connect and initialize the stage first.")
            return
        try:
            self.log(f"Moving to X={target.x:.2f} Y={target.y:.2f} Z={target.z:.2f}...", "info")
            future = self.motion_service.move_to_position_safe_z(target)
            future.result(timeout=60)
            self.on_refresh_position()
            self.log("Move complete.", "info")
        except Exception as e:
            self.log(f"Go to position error: {e}", "error")

    # ---------- live view ----------

    def _update_live_view(self):
        try:
            frame = self.camera.grab_frame()
            self.image_viewer.show_cv_image(frame)
        except Exception as e:
            self.log(f"Live view error: {e}", "error")
            self.live_timer.stop()
            self.live_running = False
            self.toolbar.btn_cam_start.setText("Camera")

    def closeEvent(self, event):
        self.log("Closing application, disconnecting hardware...", "info")

        if self.live_running:
            self.live_timer.stop()
            self.live_running = False

        try:
            if self.camera.is_connected:
                self.camera.disconnect()
        except Exception as e:
            print(f"Camera disconnect error: {e}")

        try:
            self.connection_service.shutdown()
        except Exception as e:
            print(f"Stage disconnect error: {e}")

        event.accept()
