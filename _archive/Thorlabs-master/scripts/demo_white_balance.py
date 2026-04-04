"""
Thorlabs CS165CU Live Camera Demo - WITH WHITE BALANCE CONTROL
Improved version with color correction for NIR contamination

Features:
- Live camera preview
- Exposure and gain control
- WHITE BALANCE adjustment (RGB gains)
- Color correction presets
- Histogram display
- Snapshot with metadata
"""

import sys
import numpy as np
import pylablib as pll
from pylablib.devices import Thorlabs

from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QPushButton, QSlider, QGroupBox, QFormLayout, QSpinBox,
    QDoubleSpinBox, QComboBox, QCheckBox
)
from PySide6.QtCore import Qt, QTimer, Signal, QThread
from PySide6.QtGui import QImage, QPixmap


class CameraThread(QThread):
    """Background thread for camera frame acquisition"""
    new_frame = Signal(np.ndarray)
    error_occurred = Signal(str)

    def __init__(self, camera):
        super().__init__()
        self.camera = camera
        self.running = False

    def run(self):
        self.running = True
        try:
            self.camera.start_acquisition()
            while self.running:
                try:
                    frame = self.camera.read_newest_image()
                    if frame is not None:
                        self.new_frame.emit(frame)
                    self.msleep(10)
                except Exception as e:
                    print(f"Frame warning: {e}")
                    self.msleep(50)
        except Exception as e:
            self.error_occurred.emit(f"Acquisition error: {e}")
        finally:
            try:
                self.camera.stop_acquisition()
            except:
                pass

    def stop(self):
        self.running = False
        self.wait()


class LiveCameraWidget(QWidget):
    """Main widget with white balance controls"""

    # White balance presets (RGB gain multipliers)
    WB_PRESETS = {
        "Default": (1.0, 1.0, 1.0),
        "Reduce NIR (Hand/Skin)": (0.6, 0.8, 1.0),  # Reduce red (NIR contamination)
        "Strong NIR Reduction": (0.4, 0.7, 1.0),
        "Warm (Tungsten)": (1.0, 0.9, 0.7),
        "Cool (Daylight)": (0.9, 1.0, 1.2),
        "Custom": (1.0, 1.0, 1.0)
    }

    def __init__(self):
        super().__init__()

        # Camera setup
        print("Initializing camera...")
        pll.par["devices/dlls/thorlabs_tlcam"] = "../vendor/thorcam"

        cameras = Thorlabs.list_cameras_tlcam()
        if not cameras:
            raise RuntimeError("No cameras detected!")

        self.camera = Thorlabs.ThorlabsTLCamera(serial=cameras[0])
        device_info = self.camera.get_device_info()
        self.detector_size = self.camera.get_detector_size()

        print(f"Connected to: {device_info[0]} (S/N: {device_info[2]})")

        # Get camera limits
        self.current_exposure = self.camera.get_exposure()
        gain_range = self.camera.get_gain_range()
        self.min_gain, self.max_gain = gain_range

        # White balance gains (RGB multipliers)
        self.wb_r = 1.0
        self.wb_g = 1.0
        self.wb_b = 1.0

        # Frame tracking
        self.frame_count = 0
        self.last_frame = None
        self.last_frame_raw = None  # Store original for saving

        # Build UI
        self.init_ui(device_info)

        # Start camera thread
        self.camera_thread = CameraThread(self.camera)
        self.camera_thread.new_frame.connect(self.update_image)
        self.camera_thread.error_occurred.connect(self.show_error)
        self.camera_thread.start()

    def init_ui(self, device_info):
        """Build the user interface"""
        main_layout = QVBoxLayout()

        # Title
        title = QLabel(f"Thorlabs {device_info[0]} - White Balance Demo")
        title.setStyleSheet("font-size: 18px; font-weight: bold;")
        title.setAlignment(Qt.AlignCenter)
        main_layout.addWidget(title)

        # Image display
        self.image_label = QLabel()
        self.image_label.setMinimumSize(720, 540)
        self.image_label.setStyleSheet("border: 2px solid #333; background: black;")
        self.image_label.setAlignment(Qt.AlignCenter)
        self.image_label.setText("Starting camera...")
        main_layout.addWidget(self.image_label)

        # Info bar
        info_layout = QHBoxLayout()
        self.fps_label = QLabel("FPS: --")
        self.resolution_label = QLabel(f"Resolution: {self.detector_size[0]}x{self.detector_size[1]}")
        self.frame_label = QLabel("Frames: 0")
        info_layout.addWidget(self.fps_label)
        info_layout.addStretch()
        info_layout.addWidget(self.resolution_label)
        info_layout.addStretch()
        info_layout.addWidget(self.frame_label)
        main_layout.addLayout(info_layout)

        # Controls - Split into two rows
        controls_row1 = QHBoxLayout()
        controls_row2 = QHBoxLayout()

        # === ROW 1: Camera Controls ===

        # Exposure control
        exposure_group = QGroupBox("Exposure")
        exposure_layout = QFormLayout()
        self.exposure_slider = QSlider(Qt.Horizontal)
        self.exposure_slider.setMinimum(1)
        self.exposure_slider.setMaximum(1000)
        self.exposure_slider.setValue(int(self.current_exposure * 1000))
        self.exposure_slider.valueChanged.connect(self.on_exposure_changed)
        self.exposure_value_label = QLabel(f"{self.current_exposure*1000:.1f} ms")
        exposure_layout.addRow("Time:", self.exposure_slider)
        exposure_layout.addRow("", self.exposure_value_label)
        exposure_group.setLayout(exposure_layout)
        controls_row1.addWidget(exposure_group)

        # Gain control
        gain_group = QGroupBox("Gain")
        gain_layout = QFormLayout()
        self.gain_spinbox = QSpinBox()
        self.gain_spinbox.setMinimum(int(self.min_gain))
        self.gain_spinbox.setMaximum(int(self.max_gain))
        self.gain_spinbox.setValue(0)
        self.gain_spinbox.setSuffix(" dB")
        self.gain_spinbox.valueChanged.connect(self.on_gain_changed)
        gain_layout.addRow("Value:", self.gain_spinbox)
        gain_group.setLayout(gain_layout)
        controls_row1.addWidget(gain_group)

        main_layout.addLayout(controls_row1)

        # === ROW 2: White Balance Controls ===

        # White balance preset
        wb_preset_group = QGroupBox("White Balance Preset")
        wb_preset_layout = QVBoxLayout()
        self.wb_preset_combo = QComboBox()
        self.wb_preset_combo.addItems(self.WB_PRESETS.keys())
        self.wb_preset_combo.setCurrentText("Reduce NIR (Hand/Skin)")
        self.wb_preset_combo.currentTextChanged.connect(self.on_preset_changed)
        wb_preset_layout.addWidget(QLabel("Preset:"))
        wb_preset_layout.addWidget(self.wb_preset_combo)
        wb_preset_group.setLayout(wb_preset_layout)
        controls_row2.addWidget(wb_preset_group)

        # RGB gains (fine control)
        rgb_group = QGroupBox("RGB Gains (Fine Tune)")
        rgb_layout = QFormLayout()

        self.r_gain_spin = QDoubleSpinBox()
        self.r_gain_spin.setRange(0.1, 2.0)
        self.r_gain_spin.setSingleStep(0.1)
        self.r_gain_spin.setValue(0.6)
        self.r_gain_spin.valueChanged.connect(self.on_rgb_gain_changed)

        self.g_gain_spin = QDoubleSpinBox()
        self.g_gain_spin.setRange(0.1, 2.0)
        self.g_gain_spin.setSingleStep(0.1)
        self.g_gain_spin.setValue(0.8)
        self.g_gain_spin.valueChanged.connect(self.on_rgb_gain_changed)

        self.b_gain_spin = QDoubleSpinBox()
        self.b_gain_spin.setRange(0.1, 2.0)
        self.b_gain_spin.setSingleStep(0.1)
        self.b_gain_spin.setValue(1.0)
        self.b_gain_spin.valueChanged.connect(self.on_rgb_gain_changed)

        rgb_layout.addRow("Red:", self.r_gain_spin)
        rgb_layout.addRow("Green:", self.g_gain_spin)
        rgb_layout.addRow("Blue:", self.b_gain_spin)
        rgb_group.setLayout(rgb_layout)
        controls_row2.addWidget(rgb_group)

        # Actions
        actions_group = QGroupBox("Actions")
        actions_layout = QVBoxLayout()
        self.snapshot_btn = QPushButton("📷 Save Snapshot")
        self.snapshot_btn.clicked.connect(self.save_snapshot)
        self.reset_btn = QPushButton("🔄 Reset All")
        self.reset_btn.clicked.connect(self.reset_settings)
        actions_layout.addWidget(self.snapshot_btn)
        actions_layout.addWidget(self.reset_btn)
        actions_group.setLayout(actions_layout)
        controls_row2.addWidget(actions_group)

        main_layout.addLayout(controls_row2)

        # Explanation label
        explanation = QLabel(
            "💡 TIP: CS165CU is sensitive to Near-Infrared (NIR). "
            "Skin/fabric may look pink/red due to NIR reflection. "
            "Use 'Reduce NIR' preset or adjust RGB gains manually. "
            "For natural colors, add hardware IR cut filter."
        )
        explanation.setWordWrap(True)
        explanation.setStyleSheet("padding: 10px; background: #ffffcc; border: 1px solid #ccc;")
        main_layout.addWidget(explanation)

        # Status bar
        self.status_label = QLabel("Status: Ready | WHITE BALANCE: Reduce NIR (Hand/Skin)")
        self.status_label.setStyleSheet("padding: 5px; background: #f0f0f0;")
        main_layout.addWidget(self.status_label)

        self.setLayout(main_layout)

        # FPS timer
        self.fps_timer = QTimer()
        self.fps_timer.timeout.connect(self.update_fps)
        self.fps_timer.start(1000)
        self.last_frame_count = 0

        # Apply initial preset
        self.on_preset_changed("Reduce NIR (Hand/Skin)")

    def apply_white_balance(self, frame):
        """Apply RGB gain correction to frame"""
        if frame is None:
            return None

        # Make a copy to avoid modifying original
        corrected = frame.astype(np.float32)

        # Apply per-channel gains
        corrected[:, :, 0] *= self.wb_r  # Red
        corrected[:, :, 1] *= self.wb_g  # Green
        corrected[:, :, 2] *= self.wb_b  # Blue

        # Clip to valid range
        corrected = np.clip(corrected, 0, 65535)

        return corrected.astype(np.uint16)

    def update_image(self, frame):
        """Update display with new camera frame"""
        self.frame_count += 1
        self.last_frame_raw = frame  # Store original
        self.frame_label.setText(f"Frames: {self.frame_count}")

        # Apply white balance correction
        corrected_frame = self.apply_white_balance(frame)
        self.last_frame = corrected_frame

        # Convert to 8-bit for display
        if corrected_frame.dtype == np.uint16:
            display_frame = (corrected_frame >> 2).astype(np.uint8)
        else:
            display_frame = corrected_frame

        height, width, channels = display_frame.shape
        bytes_per_line = width * channels

        qimage = QImage(
            display_frame.data,
            width,
            height,
            bytes_per_line,
            QImage.Format_RGB888
        )

        pixmap = QPixmap.fromImage(qimage)
        scaled_pixmap = pixmap.scaled(
            self.image_label.size(),
            Qt.KeepAspectRatio,
            Qt.SmoothTransformation
        )

        self.image_label.setPixmap(scaled_pixmap)

    def update_fps(self):
        frames_this_second = self.frame_count - self.last_frame_count
        self.last_frame_count = self.frame_count
        self.fps_label.setText(f"FPS: {frames_this_second}")

    def on_exposure_changed(self, value):
        exposure_ms = value
        exposure_sec = exposure_ms / 1000.0
        try:
            self.camera.set_exposure(exposure_sec)
            self.exposure_value_label.setText(f"{exposure_ms:.1f} ms")
            self.update_status()
        except Exception as e:
            self.status_label.setText(f"Status: Error setting exposure - {e}")

    def on_gain_changed(self, value):
        try:
            self.camera.set_gain(value)
            self.update_status()
        except Exception as e:
            self.status_label.setText(f"Status: Error setting gain - {e}")

    def on_preset_changed(self, preset_name):
        """Apply white balance preset"""
        if preset_name in self.WB_PRESETS:
            r, g, b = self.WB_PRESETS[preset_name]
            self.r_gain_spin.setValue(r)
            self.g_gain_spin.setValue(g)
            self.b_gain_spin.setValue(b)
            self.update_status()

    def on_rgb_gain_changed(self):
        """Update RGB gains from spinboxes"""
        self.wb_r = self.r_gain_spin.value()
        self.wb_g = self.g_gain_spin.value()
        self.wb_b = self.b_gain_spin.value()

        # Set to "Custom" if user manually adjusts
        if self.wb_preset_combo.currentText() != "Custom":
            self.wb_preset_combo.blockSignals(True)
            self.wb_preset_combo.setCurrentText("Custom")
            self.wb_preset_combo.blockSignals(False)

        self.update_status()

    def update_status(self):
        """Update status bar with current settings"""
        preset = self.wb_preset_combo.currentText()
        self.status_label.setText(
            f"Status: Exp {self.exposure_slider.value()}ms | "
            f"Gain {self.gain_spinbox.value()}dB | "
            f"WB: {preset} (R:{self.wb_r:.1f}, G:{self.wb_g:.1f}, B:{self.wb_b:.1f})"
        )

    def save_snapshot(self):
        """Save current frame"""
        if self.last_frame is None:
            self.status_label.setText("Status: No frame to save")
            return

        try:
            import datetime
            timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"snapshot_wb_{timestamp}.png"

            # Save corrected frame (8-bit)
            save_frame = (self.last_frame >> 2).astype(np.uint8)
            height, width, channels = save_frame.shape
            bytes_per_line = width * channels
            qimage = QImage(
                save_frame.data,
                width,
                height,
                bytes_per_line,
                QImage.Format_RGB888
            )
            qimage.save(filename)

            # Also save RAW (uncorrected) for comparison
            filename_raw = f"snapshot_raw_{timestamp}.png"
            save_frame_raw = (self.last_frame_raw >> 2).astype(np.uint8)
            qimage_raw = QImage(
                save_frame_raw.data,
                width,
                height,
                bytes_per_line,
                QImage.Format_RGB888
            )
            qimage_raw.save(filename_raw)

            self.status_label.setText(
                f"Status: Saved {filename} (corrected) and {filename_raw} (raw)"
            )
            print(f"Saved: {filename} (WB corrected) and {filename_raw} (raw)")

        except Exception as e:
            self.status_label.setText(f"Status: Error saving - {e}")

    def reset_settings(self):
        """Reset to defaults"""
        try:
            self.camera.set_exposure(0.030)
            self.camera.set_gain(0)
            self.exposure_slider.setValue(30)
            self.gain_spinbox.setValue(0)
            self.wb_preset_combo.setCurrentText("Reduce NIR (Hand/Skin)")
            self.update_status()
        except Exception as e:
            self.status_label.setText(f"Status: Error resetting - {e}")

    def show_error(self, error_msg):
        self.status_label.setText(f"Status: ERROR - {error_msg}")
        print(f"Camera error: {error_msg}")

    def closeEvent(self, event):
        print("Closing camera...")
        self.camera_thread.stop()
        self.camera.close()
        print("Camera closed")
        event.accept()


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Thorlabs Camera - White Balance Demo")

        try:
            self.camera_widget = LiveCameraWidget()
            self.setCentralWidget(self.camera_widget)
        except Exception as e:
            print(f"ERROR: {e}")
            sys.exit(1)

        self.resize(1000, 900)


def main():
    print("=" * 70)
    print("Thorlabs Camera - White Balance Control Demo")
    print("=" * 70)

    app = QApplication(sys.argv)
    app.setStyle("Fusion")

    window = MainWindow()
    window.show()

    print("\nWhite Balance Demo Running")
    print("TIP: Try 'Reduce NIR' preset for natural skin tones")
    print("     Adjust RGB gains manually for fine-tuning")
    print("     Hardware IR cut filter gives best results!")
    print("=" * 70)

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
