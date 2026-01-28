"""
Thorlabs CS165CU Live Camera Demo
Simple live view application using PyLabLib + PySide6

Features:
- Live camera preview (30 fps)
- Exposure control
- Gain control
- ROI display info
- Snapshot capture
"""

import sys
import numpy as np
import pylablib as pll
from pylablib.devices import Thorlabs

from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QPushButton, QSlider, QGroupBox, QFormLayout, QSpinBox
)
from PySide6.QtCore import Qt, QTimer, Signal, QThread
from PySide6.QtGui import QImage, QPixmap, QPainter, QPen, QColor


class CameraThread(QThread):
    """Background thread for camera frame acquisition"""
    new_frame = Signal(np.ndarray)  # Emits RGB frames
    error_occurred = Signal(str)

    def __init__(self, camera):
        super().__init__()
        self.camera = camera
        self.running = False

    def run(self):
        """Continuously grab frames from camera"""
        self.running = True
        try:
            self.camera.start_acquisition()

            while self.running:
                try:
                    # Non-blocking read - get newest frame
                    frame = self.camera.read_newest_image()
                    if frame is not None:
                        self.new_frame.emit(frame)
                    self.msleep(10)  # ~30 fps max

                except Exception as e:
                    # Handle occasional acquisition failures (0.1% chance)
                    print(f"Frame acquisition warning: {e}")
                    self.msleep(50)  # Brief pause on error

        except Exception as e:
            self.error_occurred.emit(f"Acquisition error: {e}")
        finally:
            try:
                self.camera.stop_acquisition()
            except:
                pass

    def stop(self):
        """Stop the acquisition thread"""
        self.running = False
        self.wait()  # Wait for thread to finish


class LiveCameraWidget(QWidget):
    """Main widget for live camera display and controls"""

    def __init__(self):
        super().__init__()

        # Camera setup
        print("Initializing camera...")
        pll.par["devices/dlls/thorlabs_tlcam"] = "../vendor/thorcam"

        cameras = Thorlabs.list_cameras_tlcam()
        if not cameras:
            raise RuntimeError("No cameras detected!")

        self.camera = Thorlabs.ThorlabsTLCamera(serial=cameras[0])

        # Get camera info
        device_info = self.camera.get_device_info()
        self.detector_size = self.camera.get_detector_size()

        print(f"Connected to: {device_info[0]} (S/N: {device_info[2]})")
        print(f"Sensor: {self.detector_size[0]}x{self.detector_size[1]} pixels")

        # Get initial settings
        self.current_exposure = self.camera.get_exposure()
        gain_range = self.camera.get_gain_range()
        self.min_gain, self.max_gain = gain_range

        # Frame counter
        self.frame_count = 0
        self.last_frame = None

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
        title = QLabel(f"Thorlabs {device_info[0]} Live View")
        title.setStyleSheet("font-size: 18px; font-weight: bold;")
        title.setAlignment(Qt.AlignCenter)
        main_layout.addWidget(title)

        # Image display
        self.image_label = QLabel()
        self.image_label.setMinimumSize(720, 540)  # Half resolution display
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

        # Controls
        controls_layout = QHBoxLayout()

        # Exposure control
        exposure_group = QGroupBox("Exposure Control")
        exposure_layout = QFormLayout()

        self.exposure_slider = QSlider(Qt.Horizontal)
        self.exposure_slider.setMinimum(1)  # 1ms
        self.exposure_slider.setMaximum(1000)  # 1000ms
        self.exposure_slider.setValue(int(self.current_exposure * 1000))
        self.exposure_slider.valueChanged.connect(self.on_exposure_changed)

        self.exposure_value_label = QLabel(f"{self.current_exposure*1000:.1f} ms")

        exposure_layout.addRow("Exposure:", self.exposure_slider)
        exposure_layout.addRow("", self.exposure_value_label)
        exposure_group.setLayout(exposure_layout)
        controls_layout.addWidget(exposure_group)

        # Gain control
        gain_group = QGroupBox("Gain Control")
        gain_layout = QFormLayout()

        self.gain_spinbox = QSpinBox()
        self.gain_spinbox.setMinimum(int(self.min_gain))
        self.gain_spinbox.setMaximum(int(self.max_gain))
        self.gain_spinbox.setValue(0)
        self.gain_spinbox.setSuffix(" dB")
        self.gain_spinbox.valueChanged.connect(self.on_gain_changed)

        gain_layout.addRow("Gain:", self.gain_spinbox)
        gain_group.setLayout(gain_layout)
        controls_layout.addWidget(gain_group)

        # Actions
        actions_group = QGroupBox("Actions")
        actions_layout = QVBoxLayout()

        self.snapshot_btn = QPushButton("📷 Save Snapshot")
        self.snapshot_btn.clicked.connect(self.save_snapshot)

        self.reset_btn = QPushButton("🔄 Reset Settings")
        self.reset_btn.clicked.connect(self.reset_settings)

        actions_layout.addWidget(self.snapshot_btn)
        actions_layout.addWidget(self.reset_btn)
        actions_group.setLayout(actions_layout)
        controls_layout.addWidget(actions_group)

        main_layout.addLayout(controls_layout)

        # Status bar
        self.status_label = QLabel("Status: Ready")
        self.status_label.setStyleSheet("padding: 5px; background: #f0f0f0;")
        main_layout.addWidget(self.status_label)

        self.setLayout(main_layout)

        # FPS calculation timer
        self.fps_timer = QTimer()
        self.fps_timer.timeout.connect(self.update_fps)
        self.fps_timer.start(1000)  # Update every second
        self.last_frame_count = 0

    def update_image(self, frame):
        """Update display with new camera frame"""
        self.frame_count += 1
        self.last_frame = frame
        self.frame_label.setText(f"Frames: {self.frame_count}")

        # Convert numpy array to QImage
        # Frame is (H, W, 3) uint16 RGB from PyLabLib
        # Scale to 8-bit for display
        if frame.dtype == np.uint16:
            # Scale 10-bit data (0-1023) to 8-bit (0-255)
            display_frame = (frame >> 2).astype(np.uint8)  # Divide by 4
        else:
            display_frame = frame

        height, width, channels = display_frame.shape
        bytes_per_line = width * channels

        qimage = QImage(
            display_frame.data,
            width,
            height,
            bytes_per_line,
            QImage.Format_RGB888
        )

        # Scale to fit display (maintain aspect ratio)
        pixmap = QPixmap.fromImage(qimage)
        scaled_pixmap = pixmap.scaled(
            self.image_label.size(),
            Qt.KeepAspectRatio,
            Qt.SmoothTransformation
        )

        self.image_label.setPixmap(scaled_pixmap)

    def update_fps(self):
        """Calculate and display FPS"""
        frames_this_second = self.frame_count - self.last_frame_count
        self.last_frame_count = self.frame_count
        self.fps_label.setText(f"FPS: {frames_this_second}")

    def on_exposure_changed(self, value):
        """Handle exposure slider change"""
        exposure_ms = value
        exposure_sec = exposure_ms / 1000.0

        try:
            self.camera.set_exposure(exposure_sec)
            self.exposure_value_label.setText(f"{exposure_ms:.1f} ms")
            self.status_label.setText(f"Status: Exposure set to {exposure_ms:.1f} ms")
        except Exception as e:
            self.status_label.setText(f"Status: Error setting exposure - {e}")

    def on_gain_changed(self, value):
        """Handle gain change"""
        try:
            self.camera.set_gain(value)
            self.status_label.setText(f"Status: Gain set to {value} dB")
        except Exception as e:
            self.status_label.setText(f"Status: Error setting gain - {e}")

    def save_snapshot(self):
        """Save current frame to file"""
        if self.last_frame is None:
            self.status_label.setText("Status: No frame to save")
            return

        try:
            import datetime
            timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"snapshot_{timestamp}.png"

            # Convert to 8-bit for saving
            if self.last_frame.dtype == np.uint16:
                save_frame = (self.last_frame >> 2).astype(np.uint8)
            else:
                save_frame = self.last_frame

            # Convert to QImage and save
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
            self.status_label.setText(f"Status: Saved {filename}")
            print(f"Snapshot saved: {filename}")

        except Exception as e:
            self.status_label.setText(f"Status: Error saving - {e}")

    def reset_settings(self):
        """Reset camera to default settings"""
        try:
            self.camera.set_exposure(0.030)  # 30ms default
            self.camera.set_gain(0)

            self.exposure_slider.setValue(30)
            self.gain_spinbox.setValue(0)

            self.status_label.setText("Status: Settings reset to defaults")
        except Exception as e:
            self.status_label.setText(f"Status: Error resetting - {e}")

    def show_error(self, error_msg):
        """Display error message"""
        self.status_label.setText(f"Status: ERROR - {error_msg}")
        print(f"Camera error: {error_msg}")

    def closeEvent(self, event):
        """Clean up when window closes"""
        print("Closing camera...")
        self.camera_thread.stop()
        self.camera.close()
        print("Camera closed successfully")
        event.accept()


class MainWindow(QMainWindow):
    """Main application window"""

    def __init__(self):
        super().__init__()
        self.setWindowTitle("Thorlabs Camera Live Demo")

        # Create central widget
        try:
            self.camera_widget = LiveCameraWidget()
            self.setCentralWidget(self.camera_widget)
        except Exception as e:
            print(f"ERROR: Failed to initialize camera: {e}")
            sys.exit(1)

        # Window size
        self.resize(900, 800)


def main():
    """Application entry point"""
    print("=" * 70)
    print("Thorlabs Camera Live Demo")
    print("PyLabLib + PySide6")
    print("=" * 70)

    app = QApplication(sys.argv)

    # Set application style
    app.setStyle("Fusion")

    # Create and show main window
    window = MainWindow()
    window.show()

    print("\nCamera is running. Close window to exit.")
    print("Controls:")
    print("  - Adjust exposure slider for brightness")
    print("  - Increase gain for low-light conditions")
    print("  - Click 'Save Snapshot' to capture current frame")
    print("=" * 70)

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
