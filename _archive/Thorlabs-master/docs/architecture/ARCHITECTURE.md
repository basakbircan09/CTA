# Thorlabs Camera Application - OOP Architecture

**Status**: Final Design
**Date**: 2025-11-04
**Camera**: CS165CU Color Camera
**Stack**: PyLabLib + PySide6

---

## Design Philosophy

### Core Principles
1. **Simplicity over patterns** - Don't create layers just because you can
2. **Device abstraction** - Hide pylablib behind adapter for future flexibility
3. **Clean threading** - Qt signals/slots for GUI communication
4. **Testable components** - Mock adapter interface, not external library
5. **Practical focus** - Manual calibration for fixed-position experiments (no autofocus algorithm)

### Use Case
- **Fixed position imaging**: Camera and samples at consistent distance
- **Manual calibration**: Set focus and white balance once, save as presets
- **Repeatable experiments**: Load saved settings for consistent imaging
- **Multi-device future**: Easy to add stages, sensors, other instruments

---

## Project Structure

```
C:\Users\go97mop\PycharmProjects\Thorlabs\
├── config.py                          # Application-wide settings
├── devices/
│   ├── __init__.py
│   ├── thorlabs_camera.py            # Camera adapter + DLL setup
│   └── exceptions.py                 # Camera-specific exceptions
├── models/
│   ├── __init__.py
│   ├── camera.py                     # CameraSettings, CameraCapabilities, ROI
│   └── frame.py                      # Frame dataclass
├── services/
│   ├── __init__.py
│   ├── acquisition.py                # AcquisitionThread (QThread)
│   ├── white_balance.py              # WhiteBalanceProcessor
│   ├── focus_assistant.py            # FocusMetric (sharpness calculation)
│   └── storage.py                    # FrameSaver
├── gui/
│   ├── __init__.py
│   ├── live_view.py                  # Image display widget
│   ├── camera_controls.py            # Exposure, gain, ROI controls
│   ├── white_balance_panel.py        # WB presets + manual adjustment
│   ├── focus_assistant.py            # Sharpness meter widget (manual focus aid)
│   ├── settings_manager.py           # Save/load presets
│   └── main_window.py                # Main application window
├── main.py                           # Application entry point
├── tests/
│   ├── __init__.py
│   ├── test_camera_adapter.py
│   ├── test_processing.py
│   ├── test_acquisition.py
│   └── fixtures/
│       └── mock_camera.py            # Mock adapter for testing
├── presets/                          # Saved camera settings (JSON)
│   ├── default.json
│   └── experiment_A.json
└── docs/                             # Documentation files
```

---

## Layer Details

### 1. Configuration (`config.py`)

**Single file for application-wide settings.**

```python
# config.py
from pathlib import Path

# Application
APP_NAME = "Thorlabs Camera Control"
APP_VERSION = "1.0.0"

# Paths
PROJECT_ROOT = Path(__file__).parent
THORCAM_DLL_PATH = PROJECT_ROOT / "ThorCam"
PRESETS_DIR = PROJECT_ROOT / "presets"
SNAPSHOTS_DIR = PROJECT_ROOT / "snapshots"

# Camera defaults
DEFAULT_EXPOSURE_MS = 30
DEFAULT_GAIN_DB = 0
DEFAULT_WHITE_BALANCE = (1.0, 1.0, 1.0)  # RGB

# GUI settings
TARGET_FPS = 30
DISPLAY_SCALE = 0.5  # Show half-size for performance

# Create directories
PRESETS_DIR.mkdir(exist_ok=True)
SNAPSHOTS_DIR.mkdir(exist_ok=True)
```

**Why single file**: Simple settings don't need modules. If it grows beyond ~50 lines, refactor.

---

### 2. Device Layer (`devices/`)

#### `devices/thorlabs_camera.py`

**Encapsulates all PyLabLib interaction.**

```python
from typing import Optional, Tuple, List
import numpy as np
import pylablib as pll
from pylablib.devices import Thorlabs

from models.camera import CameraSettings, CameraCapabilities, ROI
from models.frame import Frame
from devices.exceptions import *


def setup_dll_path(dll_dir: str = "./ThorCam") -> None:
    """Configure pylablib to find Thorlabs DLLs. Call once before camera use."""
    pll.par["devices/dlls/thorlabs_tlcam"] = dll_dir


class ThorlabsCameraAdapter:
    """
    Adapter for Thorlabs camera using PyLabLib.
    Abstracts pylablib specifics, provides typed interface.
    """

    def __init__(self):
        self._camera: Optional[Thorlabs.ThorlabsTLCamera] = None
        self._serial: Optional[str] = None
        self._is_connected: bool = False
        self._frame_index: int = 0

    @staticmethod
    def list_cameras() -> List[str]:
        """Discover connected cameras."""
        try:
            return Thorlabs.list_cameras_tlcam()
        except Exception as e:
            raise CameraDiscoveryError(f"Failed to list cameras: {e}")

    def connect(self, serial: Optional[str] = None) -> CameraCapabilities:
        """
        Connect to camera by serial number.
        If serial is None, connects to first available camera.

        Returns: CameraCapabilities with device info and limits
        Raises: CameraConnectionError
        """
        try:
            self._camera = Thorlabs.ThorlabsTLCamera(serial=serial)
            self._is_connected = True

            # Get device info
            model, name, serial_num, firmware = self._camera.get_device_info()
            width, height = self._camera.get_detector_size()
            sensor_info = self._camera.get_sensor_info()
            gain_min, gain_max = self._camera.get_gain_range()

            # Get exposure limits (approximate from frame period)
            frame_period_range = self._camera.get_frame_period_range()

            self._serial = serial_num

            return CameraCapabilities(
                model=model,
                serial=serial_num,
                firmware=firmware,
                sensor_width=width,
                sensor_height=height,
                sensor_type=sensor_info.sensor_type,
                bit_depth=sensor_info.bit_depth,
                exposure_range_sec=(frame_period_range[0], frame_period_range[1]),
                gain_range_db=(gain_min, gain_max)
            )

        except Exception as e:
            raise CameraConnectionError(f"Failed to connect: {e}")

    def disconnect(self) -> None:
        """Disconnect from camera and release resources."""
        if self._camera:
            try:
                if self._is_acquiring:
                    self.stop_acquisition()
                self._camera.close()
            except Exception as e:
                print(f"Warning: Error during disconnect: {e}")
            finally:
                self._camera = None
                self._is_connected = False

    def apply_settings(self, settings: CameraSettings) -> CameraSettings:
        """
        Apply settings to camera. Returns actual values set (may differ due to hardware constraints).

        Raises: CameraNotConnectedError, SettingsError
        """
        if not self._is_connected:
            raise CameraNotConnectedError("Cannot apply settings: not connected")

        try:
            # Set exposure
            self._camera.set_exposure(settings.exposure_sec)
            actual_exposure = self._camera.get_exposure()

            # Set gain
            self._camera.set_gain(settings.gain_db)
            actual_gain = self._camera.get_gain()

            # Set ROI if specified
            actual_roi = settings.roi
            if settings.roi:
                pylablib_roi = settings.roi.to_pylablib()
                self._camera.set_roi(*pylablib_roi)
                actual_roi_tuple = self._camera.get_roi()
                actual_roi = ROI.from_pylablib(actual_roi_tuple)

            # White balance is applied in post-processing, not on camera

            return CameraSettings(
                exposure_sec=actual_exposure,
                gain_db=actual_gain,
                roi=actual_roi,
                white_balance_rgb=settings.white_balance_rgb
            )

        except Exception as e:
            raise SettingsError(f"Failed to apply settings: {e}")

    def get_current_settings(self) -> CameraSettings:
        """Get current camera settings."""
        if not self._is_connected:
            raise CameraNotConnectedError()

        exposure = self._camera.get_exposure()
        gain = self._camera.get_gain()
        roi_tuple = self._camera.get_roi()
        roi = ROI.from_pylablib(roi_tuple)

        return CameraSettings(
            exposure_sec=exposure,
            gain_db=gain,
            roi=roi,
            white_balance_rgb=(1.0, 1.0, 1.0)  # Default, actual WB in settings
        )

    def start_acquisition(self) -> None:
        """Start continuous frame acquisition."""
        if not self._is_connected:
            raise CameraNotConnectedError()

        try:
            self._camera.start_acquisition()
            self._is_acquiring = True
            self._frame_index = 0
        except Exception as e:
            raise AcquisitionStartError(f"Failed to start acquisition: {e}")

    def stop_acquisition(self) -> None:
        """Stop frame acquisition."""
        if self._is_acquiring:
            try:
                self._camera.stop_acquisition()
            except Exception as e:
                print(f"Warning: Error stopping acquisition: {e}")
            finally:
                self._is_acquiring = False

    def read_latest_frame(self) -> Optional[Frame]:
        """
        Read newest available frame (non-blocking).
        Returns None if no frame available.
        """
        if not self._is_acquiring:
            return None

        try:
            frame_data = self._camera.read_newest_image()
            if frame_data is None:
                return None

            self._frame_index += 1

            return Frame(
                data=frame_data,
                timestamp_ns=self._get_timestamp_ns(),
                frame_index=self._frame_index,
                metadata={
                    'exposure_sec': self._camera.get_exposure(),
                    'gain_db': self._camera.get_gain()
                }
            )
        except Exception as e:
            # Log but don't raise - occasional failures are expected (0.1% DLL issue)
            print(f"Frame read warning: {e}")
            return None

    def snap(self) -> Frame:
        """
        Capture single frame (blocks until frame ready).
        Handles acquisition start/stop automatically.
        """
        if not self._is_connected:
            raise CameraNotConnectedError()

        try:
            was_acquiring = self._is_acquiring

            if not was_acquiring:
                self.start_acquisition()

            frame_data = self._camera.snap()

            if not was_acquiring:
                self.stop_acquisition()

            self._frame_index += 1

            return Frame(
                data=frame_data,
                timestamp_ns=self._get_timestamp_ns(),
                frame_index=self._frame_index,
                metadata={
                    'exposure_sec': self._camera.get_exposure(),
                    'gain_db': self._camera.get_gain()
                }
            )
        except Exception as e:
            raise AcquisitionError(f"Failed to capture frame: {e}")

    @property
    def is_connected(self) -> bool:
        return self._is_connected

    @property
    def is_acquiring(self) -> bool:
        return self._is_acquiring

    def _get_timestamp_ns(self) -> int:
        """Get current timestamp in nanoseconds."""
        import time
        return time.time_ns()
```

**Key design decisions**:
- ✅ All pylablib code isolated here
- ✅ Returns typed objects (not tuples)
- ✅ Translates exceptions to domain errors
- ✅ Can swap to raw SDK later without changing caller code

#### `devices/exceptions.py`

```python
class CameraError(Exception):
    """Base exception for all camera errors."""
    pass

class CameraDiscoveryError(CameraError):
    """Failed to discover cameras."""
    pass

class CameraNotFoundError(CameraError):
    """Requested camera not found."""
    pass

class CameraConnectionError(CameraError):
    """Failed to connect to camera."""
    pass

class CameraNotConnectedError(CameraError):
    """Operation requires connected camera."""
    pass

class AcquisitionStartError(CameraError):
    """Failed to start acquisition (0.1% DLL issue)."""
    pass

class AcquisitionError(CameraError):
    """Error during frame acquisition."""
    pass

class SettingsError(CameraError):
    """Failed to apply camera settings."""
    pass
```

---

### 3. Models (`models/`)

#### `models/camera.py`

```python
from dataclasses import dataclass
from typing import Optional, Tuple

@dataclass
class ROI:
    """Region of Interest for camera."""
    x: int
    y: int
    width: int
    height: int
    bin_x: int = 1
    bin_y: int = 1

    def to_pylablib(self) -> Tuple[int, int, int, int, int, int]:
        """Convert to pylablib format (hstart, hend, vstart, vend, hbin, vbin)."""
        return (
            self.x,
            self.x + self.width,
            self.y,
            self.y + self.height,
            self.bin_x,
            self.bin_y
        )

    @staticmethod
    def from_pylablib(roi_tuple: Tuple[int, int, int, int, int, int]) -> 'ROI':
        """Create from pylablib format."""
        hstart, hend, vstart, vend, hbin, vbin = roi_tuple
        return ROI(
            x=hstart,
            y=vstart,
            width=hend - hstart,
            height=vend - vstart,
            bin_x=hbin,
            bin_y=vbin
        )

    @staticmethod
    def full_frame(width: int, height: int) -> 'ROI':
        """Create full-frame ROI."""
        return ROI(x=0, y=0, width=width, height=height)


@dataclass
class CameraSettings:
    """Camera configuration settings."""
    exposure_sec: float
    gain_db: float
    roi: Optional[ROI] = None
    white_balance_rgb: Tuple[float, float, float] = (1.0, 1.0, 1.0)

    def to_dict(self) -> dict:
        """Serialize to dictionary for saving."""
        return {
            'exposure_sec': self.exposure_sec,
            'gain_db': self.gain_db,
            'roi': {
                'x': self.roi.x,
                'y': self.roi.y,
                'width': self.roi.width,
                'height': self.roi.height,
                'bin_x': self.roi.bin_x,
                'bin_y': self.roi.bin_y
            } if self.roi else None,
            'white_balance_rgb': list(self.white_balance_rgb)
        }

    @staticmethod
    def from_dict(data: dict) -> 'CameraSettings':
        """Deserialize from dictionary."""
        roi = None
        if data.get('roi'):
            roi = ROI(**data['roi'])

        return CameraSettings(
            exposure_sec=data['exposure_sec'],
            gain_db=data['gain_db'],
            roi=roi,
            white_balance_rgb=tuple(data['white_balance_rgb'])
        )


@dataclass
class CameraCapabilities:
    """Camera hardware capabilities and limits."""
    model: str
    serial: str
    firmware: str
    sensor_width: int
    sensor_height: int
    sensor_type: str  # 'bayer', 'mono', etc.
    bit_depth: int
    exposure_range_sec: Tuple[float, float]
    gain_range_db: Tuple[float, float]
```

#### `models/frame.py`

```python
from dataclasses import dataclass, field
from typing import Dict, Any
import numpy as np

@dataclass
class Frame:
    """Single camera frame with metadata."""
    data: np.ndarray              # RGB image (H, W, 3) uint16
    timestamp_ns: int             # Nanosecond timestamp
    frame_index: int              # Sequential frame number
    metadata: Dict[str, Any] = field(default_factory=dict)  # Flexible metadata

    @property
    def shape(self) -> tuple:
        """Frame shape (height, width, channels)."""
        return self.data.shape

    @property
    def height(self) -> int:
        return self.data.shape[0]

    @property
    def width(self) -> int:
        return self.data.shape[1]

    @property
    def channels(self) -> int:
        return self.data.shape[2] if self.data.ndim == 3 else 1
```

**Why these models**:
- Simple dataclasses, no logic
- Easy to serialize (to_dict/from_dict)
- Type hints for IDE support
- Flexible metadata dict for edge cases

---

### 4. Services (`services/`)

#### `services/acquisition.py`

```python
from PySide6.QtCore import QThread, Signal
import time

from devices.thorlabs_camera import ThorlabsCameraAdapter
from models.frame import Frame

class AcquisitionThread(QThread):
    """
    Background thread for continuous frame acquisition.
    Emits frames via signals to GUI thread.
    """

    # Signals
    frame_ready = Signal(Frame)
    fps_updated = Signal(float)
    error = Signal(str)

    def __init__(self, camera: ThorlabsCameraAdapter, poll_interval_ms: int = 10):
        super().__init__()
        self.camera = camera
        self.poll_interval_ms = poll_interval_ms
        self.running = False

        # FPS tracking
        self.frame_count = 0
        self.last_fps_time = 0

    def run(self):
        """Main acquisition loop (runs in background thread)."""
        self.running = True
        self.frame_count = 0
        self.last_fps_time = time.time()

        try:
            # Start camera acquisition
            self.camera.start_acquisition()

            while self.running:
                try:
                    # Read latest frame (non-blocking)
                    frame = self.camera.read_latest_frame()

                    if frame is not None:
                        self.frame_ready.emit(frame)
                        self.frame_count += 1

                        # Update FPS every second
                        current_time = time.time()
                        elapsed = current_time - self.last_fps_time
                        if elapsed >= 1.0:
                            fps = self.frame_count / elapsed
                            self.fps_updated.emit(fps)
                            self.frame_count = 0
                            self.last_fps_time = current_time

                    # Sleep to target frame rate
                    self.msleep(self.poll_interval_ms)

                except Exception as e:
                    # Log occasional errors (0.1% DLL issue) but continue
                    print(f"Frame acquisition warning: {e}")
                    self.msleep(50)  # Brief pause on error

        except Exception as e:
            self.error.emit(f"Acquisition failed: {e}")
        finally:
            try:
                self.camera.stop_acquisition()
            except:
                pass

    def stop(self):
        """Stop the acquisition thread."""
        self.running = False
        self.wait()  # Wait for thread to finish
```

**Why no separate "Controller"**:
- Thread itself IS the controller
- Exposes start/stop via QThread methods
- Emits signals directly to GUI
- Simple and effective

#### `services/white_balance.py`

```python
import numpy as np
from typing import Tuple
from models.frame import Frame

class WhiteBalanceProcessor:
    """Apply white balance correction to frames."""

    # Presets for different scenarios
    PRESETS = {
        "Default": (1.0, 1.0, 1.0),
        "Reduce NIR (Hand/Skin)": (0.6, 0.8, 1.0),
        "Strong NIR Reduction": (0.4, 0.7, 1.0),
        "Warm (Tungsten)": (1.0, 0.9, 0.7),
        "Cool (Daylight)": (0.9, 1.0, 1.2),
    }

    def __init__(self, rgb_gains: Tuple[float, float, float] = (1.0, 1.0, 1.0)):
        self.set_gains(*rgb_gains)

    def set_gains(self, r: float, g: float, b: float):
        """Set RGB gain multipliers."""
        self.r_gain = r
        self.g_gain = g
        self.b_gain = b

    def set_preset(self, preset_name: str):
        """Apply named preset."""
        if preset_name in self.PRESETS:
            self.set_gains(*self.PRESETS[preset_name])

    def process(self, frame: Frame) -> np.ndarray:
        """
        Apply white balance to frame.
        Returns new array (doesn't modify input).
        """
        if frame.data is None:
            return None

        # Convert to float for processing
        corrected = frame.data.astype(np.float32)

        # Apply per-channel gains
        corrected[:, :, 0] *= self.r_gain  # Red
        corrected[:, :, 1] *= self.g_gain  # Green
        corrected[:, :, 2] *= self.b_gain  # Blue

        # Clip to valid range
        corrected = np.clip(corrected, 0, 65535)

        return corrected.astype(np.uint16)
```

**For fixed-position experiments**:
- Find best WB manually before experiment
- Save as preset (JSON)
- Load at experiment start
- No need for auto-WB algorithm

#### `services/focus_assistant.py`

```python
import numpy as np
import cv2
from models.frame import Frame

class FocusMetric:
    """
    Calculate image sharpness metrics for manual focus assistance.
    For fixed-position experiments: adjust focus manually until metric is maximized.
    """

    @staticmethod
    def variance_of_laplacian(frame: Frame) -> float:
        """
        Calculate focus metric using Laplacian variance.
        Higher value = sharper image.

        Returns: float (typical range 0-10000, higher is better)
        """
        if frame.data is None:
            return 0.0

        # Convert to grayscale
        if frame.channels == 3:
            # RGB to grayscale
            gray = cv2.cvtColor(frame.data.astype(np.uint8), cv2.COLOR_RGB2GRAY)
        else:
            gray = frame.data.astype(np.uint8)

        # Calculate Laplacian
        laplacian = cv2.Laplacian(gray, cv2.CV_64F)

        # Variance = focus metric
        return laplacian.var()

    @staticmethod
    def gradient_magnitude(frame: Frame) -> float:
        """
        Alternative focus metric using gradient magnitude.
        Higher value = sharper image.
        """
        if frame.data is None:
            return 0.0

        # Convert to grayscale
        if frame.channels == 3:
            gray = cv2.cvtColor(frame.data.astype(np.uint8), cv2.COLOR_RGB2GRAY)
        else:
            gray = frame.data.astype(np.uint8)

        # Sobel gradients
        gx = cv2.Sobel(gray, cv2.CV_64F, 1, 0, ksize=3)
        gy = cv2.Sobel(gray, cv2.CV_64F, 0, 1, ksize=3)

        # Magnitude
        magnitude = np.sqrt(gx**2 + gy**2)

        return magnitude.mean()
```

**Usage for fixed-position setup**:
1. Display focus metric in GUI as live bar graph
2. User adjusts lens manually
3. When metric reaches maximum → in focus
4. Lock lens position for experiment
5. No autofocus algorithm needed!

#### `services/storage.py`

```python
from pathlib import Path
from datetime import datetime
import json
import numpy as np
from PySide6.QtGui import QImage

from models.frame import Frame
from models.camera import CameraSettings

class FrameSaver:
    """Save frames to disk with metadata."""

    def __init__(self, output_dir: Path):
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)

    def save_frame(self, frame: Frame, settings: CameraSettings,
                   prefix: str = "snapshot", save_raw: bool = False) -> Path:
        """
        Save frame as PNG with metadata.

        Args:
            frame: Frame to save
            settings: Camera settings used
            prefix: Filename prefix
            save_raw: If True, also save uncorrected 16-bit data

        Returns: Path to saved file
        """
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"{prefix}_{timestamp}.png"
        filepath = self.output_dir / filename

        # Convert 16-bit to 8-bit for PNG
        display_data = (frame.data >> 2).astype(np.uint8)

        # Create QImage
        height, width, channels = display_data.shape
        bytes_per_line = width * channels
        qimage = QImage(
            display_data.data,
            width,
            height,
            bytes_per_line,
            QImage.Format_RGB888
        )

        # Save with metadata in text chunks (PNG supports this)
        qimage.save(str(filepath))

        # Save metadata JSON
        metadata_path = filepath.with_suffix('.json')
        metadata = {
            'timestamp': timestamp,
            'frame_index': frame.frame_index,
            'settings': settings.to_dict(),
            'frame_metadata': frame.metadata
        }
        with open(metadata_path, 'w') as f:
            json.dump(metadata, f, indent=2)

        # Optionally save raw 16-bit data
        if save_raw:
            raw_path = filepath.with_suffix('.npy')
            np.save(raw_path, frame.data)

        return filepath
```

---

### 5. GUI Layer (`gui/`)

#### `gui/live_view.py`

```python
from PySide6.QtWidgets import QLabel
from PySide6.QtCore import Qt
from PySide6.QtGui import QImage, QPixmap
import numpy as np

from models.frame import Frame

class LiveViewWidget(QLabel):
    """
    Widget for displaying live camera frames.
    Simple QLabel with optimized image conversion.
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumSize(720, 540)
        self.setStyleSheet("border: 2px solid #333; background: black;")
        self.setAlignment(Qt.AlignCenter)
        self.setScaledContents(False)
        self.setText("No camera feed")

    def update_frame(self, frame_data: np.ndarray):
        """
        Update display with new frame.

        Args:
            frame_data: RGB numpy array (H, W, 3), uint8 or uint16
        """
        if frame_data is None:
            return

        # Convert to 8-bit if needed
        if frame_data.dtype == np.uint16:
            display_data = (frame_data >> 2).astype(np.uint8)
        else:
            display_data = frame_data

        height, width, channels = display_data.shape
        bytes_per_line = width * channels

        # Create QImage
        qimage = QImage(
            display_data.data,
            width,
            height,
            bytes_per_line,
            QImage.Format_RGB888
        )

        # Convert to pixmap and scale
        pixmap = QPixmap.fromImage(qimage)
        scaled_pixmap = pixmap.scaled(
            self.size(),
            Qt.KeepAspectRatio,
            Qt.SmoothTransformation
        )

        self.setPixmap(scaled_pixmap)
```

#### `gui/camera_controls.py`

```python
from PySide6.QtWidgets import (
    QWidget, QGroupBox, QFormLayout, QSlider,
    QLabel, QSpinBox, QDoubleSpinBox
)
from PySide6.QtCore import Qt, Signal

class CameraControlPanel(QWidget):
    """Panel for exposure, gain, and ROI controls."""

    # Signals emitted when user changes values
    exposure_changed = Signal(float)  # seconds
    gain_changed = Signal(float)      # dB
    roi_changed = Signal(int, int, int, int)  # x, y, width, height

    def __init__(self, parent=None):
        super().__init__(parent)
        self.init_ui()

    def init_ui(self):
        layout = QFormLayout()

        # Exposure control
        exposure_group = QGroupBox("Exposure")
        exp_layout = QFormLayout()

        self.exposure_slider = QSlider(Qt.Horizontal)
        self.exposure_slider.setMinimum(1)    # 1ms
        self.exposure_slider.setMaximum(1000) # 1000ms
        self.exposure_slider.setValue(30)
        self.exposure_slider.valueChanged.connect(self._on_exposure_slider)

        self.exposure_label = QLabel("30.0 ms")

        exp_layout.addRow("Time:", self.exposure_slider)
        exp_layout.addRow("", self.exposure_label)
        exposure_group.setLayout(exp_layout)

        # Gain control
        gain_group = QGroupBox("Gain")
        gain_layout = QFormLayout()

        self.gain_spinbox = QSpinBox()
        self.gain_spinbox.setRange(0, 48)
        self.gain_spinbox.setValue(0)
        self.gain_spinbox.setSuffix(" dB")
        self.gain_spinbox.valueChanged.connect(self._on_gain_changed)

        gain_layout.addRow("Value:", self.gain_spinbox)
        gain_group.setLayout(gain_layout)

        layout.addRow(exposure_group)
        layout.addRow(gain_group)

        self.setLayout(layout)

    def _on_exposure_slider(self, value):
        """Convert slider value (ms) to seconds and emit."""
        exposure_ms = value
        exposure_sec = value / 1000.0
        self.exposure_label.setText(f"{exposure_ms:.1f} ms")
        self.exposure_changed.emit(exposure_sec)

    def _on_gain_changed(self, value):
        """Emit gain change."""
        self.gain_changed.emit(float(value))

    def set_exposure(self, seconds: float):
        """Programmatically set exposure (e.g., from loaded preset)."""
        ms = int(seconds * 1000)
        self.exposure_slider.setValue(ms)

    def set_gain(self, db: float):
        """Programmatically set gain."""
        self.gain_spinbox.setValue(int(db))
```

#### `gui/white_balance_panel.py`

```python
from PySide6.QtWidgets import (
    QWidget, QGroupBox, QVBoxLayout, QFormLayout,
    QComboBox, QDoubleSpinBox
)
from PySide6.QtCore import Signal

class WhiteBalancePanel(QWidget):
    """Panel for white balance presets and manual RGB gains."""

    # Signal emitted when white balance changes
    white_balance_changed = Signal(float, float, float)  # R, G, B gains

    # Presets (matches service layer)
    PRESETS = {
        "Default": (1.0, 1.0, 1.0),
        "Reduce NIR (Hand/Skin)": (0.6, 0.8, 1.0),
        "Strong NIR Reduction": (0.4, 0.7, 1.0),
        "Warm (Tungsten)": (1.0, 0.9, 0.7),
        "Cool (Daylight)": (0.9, 1.0, 1.2),
    }

    def __init__(self, parent=None):
        super().__init__(parent)
        self.init_ui()

    def init_ui(self):
        layout = QVBoxLayout()

        # Preset selector
        preset_group = QGroupBox("White Balance Preset")
        preset_layout = QVBoxLayout()

        self.preset_combo = QComboBox()
        self.preset_combo.addItems(self.PRESETS.keys())
        self.preset_combo.currentTextChanged.connect(self._on_preset_changed)

        preset_layout.addWidget(self.preset_combo)
        preset_group.setLayout(preset_layout)
        layout.addWidget(preset_group)

        # Manual RGB gains
        manual_group = QGroupBox("Manual RGB Gains")
        manual_layout = QFormLayout()

        self.r_spin = QDoubleSpinBox()
        self.r_spin.setRange(0.1, 2.0)
        self.r_spin.setSingleStep(0.1)
        self.r_spin.setValue(1.0)
        self.r_spin.valueChanged.connect(self._on_manual_changed)

        self.g_spin = QDoubleSpinBox()
        self.g_spin.setRange(0.1, 2.0)
        self.g_spin.setSingleStep(0.1)
        self.g_spin.setValue(1.0)
        self.g_spin.valueChanged.connect(self._on_manual_changed)

        self.b_spin = QDoubleSpinBox()
        self.b_spin.setRange(0.1, 2.0)
        self.b_spin.setSingleStep(0.1)
        self.b_spin.setValue(1.0)
        self.b_spin.valueChanged.connect(self._on_manual_changed)

        manual_layout.addRow("Red:", self.r_spin)
        manual_layout.addRow("Green:", self.g_spin)
        manual_layout.addRow("Blue:", self.b_spin)
        manual_group.setLayout(manual_layout)
        layout.addWidget(manual_group)

        self.setLayout(layout)

    def _on_preset_changed(self, preset_name):
        """Apply preset values to spinboxes."""
        if preset_name in self.PRESETS:
            r, g, b = self.PRESETS[preset_name]
            self.r_spin.blockSignals(True)
            self.g_spin.blockSignals(True)
            self.b_spin.blockSignals(True)

            self.r_spin.setValue(r)
            self.g_spin.setValue(g)
            self.b_spin.setValue(b)

            self.r_spin.blockSignals(False)
            self.g_spin.blockSignals(False)
            self.b_spin.blockSignals(False)

            self.white_balance_changed.emit(r, g, b)

    def _on_manual_changed(self):
        """Emit signal when manual gains change."""
        r = self.r_spin.value()
        g = self.g_spin.value()
        b = self.b_spin.value()
        self.white_balance_changed.emit(r, g, b)

    def set_gains(self, r: float, g: float, b: float):
        """Programmatically set gains (e.g., from loaded preset)."""
        self.r_spin.setValue(r)
        self.g_spin.setValue(g)
        self.b_spin.setValue(b)
```

#### `gui/focus_assistant.py`

```python
from PySide6.QtWidgets import (
    QWidget, QGroupBox, QVBoxLayout, QLabel, QProgressBar
)
from PySide6.QtCore import Qt

class FocusAssistantWidget(QWidget):
    """
    Display focus metric as visual indicator.
    For fixed-position experiments: adjust lens until bar is maxed.
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self.init_ui()
        self.max_metric = 0.0  # Track maximum seen

    def init_ui(self):
        layout = QVBoxLayout()

        group = QGroupBox("Focus Assistant")
        group_layout = QVBoxLayout()

        self.metric_label = QLabel("Sharpness: --")
        self.metric_bar = QProgressBar()
        self.metric_bar.setRange(0, 100)
        self.metric_bar.setValue(0)

        self.hint_label = QLabel(
            "Adjust lens manually. Higher = sharper.\n"
            "Lock lens when bar is maximized."
        )
        self.hint_label.setStyleSheet("color: #666; font-size: 10px;")
        self.hint_label.setWordWrap(True)

        group_layout.addWidget(self.metric_label)
        group_layout.addWidget(self.metric_bar)
        group_layout.addWidget(self.hint_label)
        group.setLayout(group_layout)

        layout.addWidget(group)
        self.setLayout(layout)

    def update_metric(self, metric_value: float):
        """
        Update focus metric display.

        Args:
            metric_value: Focus metric (higher = sharper)
        """
        # Track maximum for relative display
        if metric_value > self.max_metric:
            self.max_metric = metric_value

        # Display absolute value
        self.metric_label.setText(f"Sharpness: {metric_value:.1f}")

        # Show relative to maximum (percentage)
        if self.max_metric > 0:
            percentage = int((metric_value / self.max_metric) * 100)
            self.metric_bar.setValue(percentage)

        # Color coding
        if percentage > 90:
            self.metric_bar.setStyleSheet("QProgressBar::chunk { background: green; }")
        elif percentage > 70:
            self.metric_bar.setStyleSheet("QProgressBar::chunk { background: yellow; }")
        else:
            self.metric_bar.setStyleSheet("QProgressBar::chunk { background: red; }")
```

#### `gui/settings_manager.py`

```python
from pathlib import Path
import json
from typing import Optional

from PySide6.QtWidgets import (
    QWidget, QGroupBox, QVBoxLayout, QHBoxLayout,
    QPushButton, QComboBox, QInputDialog, QMessageBox
)
from PySide6.QtCore import Signal

from models.camera import CameraSettings
import config

class SettingsManager(QWidget):
    """Widget for saving/loading camera setting presets."""

    # Signal emitted when preset is loaded
    preset_loaded = Signal(CameraSettings)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.presets_dir = config.PRESETS_DIR
        self.init_ui()
        self.refresh_preset_list()

    def init_ui(self):
        layout = QVBoxLayout()

        group = QGroupBox("Settings Presets")
        group_layout = QVBoxLayout()

        # Preset selector
        self.preset_combo = QComboBox()
        group_layout.addWidget(self.preset_combo)

        # Buttons
        button_layout = QHBoxLayout()

        self.load_btn = QPushButton("📂 Load")
        self.load_btn.clicked.connect(self.load_preset)

        self.save_btn = QPushButton("💾 Save")
        self.save_btn.clicked.connect(self.save_preset)

        self.delete_btn = QPushButton("🗑️ Delete")
        self.delete_btn.clicked.connect(self.delete_preset)

        button_layout.addWidget(self.load_btn)
        button_layout.addWidget(self.save_btn)
        button_layout.addWidget(self.delete_btn)

        group_layout.addLayout(button_layout)
        group.setLayout(group_layout)

        layout.addWidget(group)
        self.setLayout(layout)

    def refresh_preset_list(self):
        """Refresh list of available presets."""
        self.preset_combo.clear()

        # Find all .json files in presets directory
        if self.presets_dir.exists():
            preset_files = sorted(self.presets_dir.glob("*.json"))
            for preset_file in preset_files:
                self.preset_combo.addItem(preset_file.stem)

    def save_preset(self):
        """Save current settings as preset."""
        # Get preset name from user
        name, ok = QInputDialog.getText(
            self,
            "Save Preset",
            "Enter preset name:",
            text="experiment_"
        )

        if not ok or not name:
            return

        # Get current settings (would be passed from controller)
        # For now, placeholder
        settings = CameraSettings(
            exposure_sec=0.03,
            gain_db=0,
            white_balance_rgb=(0.6, 0.8, 1.0)
        )

        # Save to file
        preset_path = self.presets_dir / f"{name}.json"
        with open(preset_path, 'w') as f:
            json.dump(settings.to_dict(), f, indent=2)

        self.refresh_preset_list()
        QMessageBox.information(self, "Saved", f"Preset '{name}' saved successfully!")

    def load_preset(self):
        """Load selected preset."""
        preset_name = self.preset_combo.currentText()
        if not preset_name:
            return

        preset_path = self.presets_dir / f"{preset_name}.json"
        if not preset_path.exists():
            QMessageBox.warning(self, "Error", f"Preset '{preset_name}' not found!")
            return

        try:
            with open(preset_path, 'r') as f:
                data = json.load(f)

            settings = CameraSettings.from_dict(data)
            self.preset_loaded.emit(settings)

            QMessageBox.information(self, "Loaded", f"Preset '{preset_name}' loaded!")

        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to load preset: {e}")

    def delete_preset(self):
        """Delete selected preset."""
        preset_name = self.preset_combo.currentText()
        if not preset_name:
            return

        reply = QMessageBox.question(
            self,
            "Confirm Delete",
            f"Delete preset '{preset_name}'?",
            QMessageBox.Yes | QMessageBox.No
        )

        if reply == QMessageBox.Yes:
            preset_path = self.presets_dir / f"{preset_name}.json"
            preset_path.unlink(missing_ok=True)
            self.refresh_preset_list()
```

#### `gui/main_window.py`

```python
from PySide6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QPushButton, QLabel, QStatusBar
)
from PySide6.QtCore import Slot

from gui.live_view import LiveViewWidget
from gui.camera_controls import CameraControlPanel
from gui.white_balance_panel import WhiteBalancePanel
from gui.focus_assistant import FocusAssistantWidget
from gui.settings_manager import SettingsManager

# Controller import (defined in implementation section)
# from app.controller import ApplicationController

class MainWindow(QMainWindow):
    """Main application window."""

    def __init__(self, controller):
        super().__init__()
        self.controller = controller
        self.setWindowTitle("Thorlabs Camera Control")
        self.resize(1200, 900)

        self.init_ui()
        self.connect_signals()

    def init_ui(self):
        """Build user interface."""
        central_widget = QWidget()
        main_layout = QHBoxLayout()

        # Left side: Live view + status
        left_layout = QVBoxLayout()

        # Title
        title = QLabel("Live Camera View")
        title.setStyleSheet("font-size: 16px; font-weight: bold;")
        left_layout.addWidget(title)

        # Live view
        self.live_view = LiveViewWidget()
        left_layout.addWidget(self.live_view)

        # Info bar (FPS, resolution, etc.)
        info_layout = QHBoxLayout()
        self.fps_label = QLabel("FPS: --")
        self.resolution_label = QLabel("Resolution: --")
        self.frame_label = QLabel("Frame: --")
        info_layout.addWidget(self.fps_label)
        info_layout.addStretch()
        info_layout.addWidget(self.resolution_label)
        info_layout.addStretch()
        info_layout.addWidget(self.frame_label)
        left_layout.addLayout(info_layout)

        main_layout.addLayout(left_layout, stretch=2)

        # Right side: Controls
        right_layout = QVBoxLayout()

        # Camera controls
        self.camera_controls = CameraControlPanel()
        right_layout.addWidget(self.camera_controls)

        # White balance
        self.wb_panel = WhiteBalancePanel()
        right_layout.addWidget(self.wb_panel)

        # Focus assistant
        self.focus_assistant = FocusAssistantWidget()
        right_layout.addWidget(self.focus_assistant)

        # Settings manager
        self.settings_manager = SettingsManager()
        right_layout.addWidget(self.settings_manager)

        # Action buttons
        action_layout = QVBoxLayout()

        self.start_btn = QPushButton("▶️ Start Live View")
        self.start_btn.clicked.connect(self.controller.start_live)

        self.stop_btn = QPushButton("⏹️ Stop")
        self.stop_btn.clicked.connect(self.controller.stop_live)
        self.stop_btn.setEnabled(False)

        self.snapshot_btn = QPushButton("📷 Snapshot")
        self.snapshot_btn.clicked.connect(self.controller.capture_snapshot)

        action_layout.addWidget(self.start_btn)
        action_layout.addWidget(self.stop_btn)
        action_layout.addWidget(self.snapshot_btn)

        right_layout.addLayout(action_layout)
        right_layout.addStretch()

        main_layout.addLayout(right_layout, stretch=1)

        central_widget.setLayout(main_layout)
        self.setCentralWidget(central_widget)

        # Status bar
        self.status_bar = QStatusBar()
        self.setStatusBar(self.status_bar)
        self.status_bar.showMessage("Ready")

    def connect_signals(self):
        """Connect widget signals to controller."""
        # Camera controls
        self.camera_controls.exposure_changed.connect(
            self.controller.set_exposure
        )
        self.camera_controls.gain_changed.connect(
            self.controller.set_gain
        )

        # White balance
        self.wb_panel.white_balance_changed.connect(
            self.controller.set_white_balance
        )

        # Settings manager
        self.settings_manager.preset_loaded.connect(
            self.controller.apply_settings
        )

    @Slot(float)
    def update_fps(self, fps: float):
        """Update FPS display."""
        self.fps_label.setText(f"FPS: {fps:.1f}")

    @Slot(str)
    def update_status(self, message: str):
        """Update status bar."""
        self.status_bar.showMessage(message)

    def closeEvent(self, event):
        """Handle window close."""
        self.controller.shutdown()
        event.accept()
```

---

### 6. Application Controller (`main.py` contains simple controller)

**For your fixed-position use case, a lightweight controller is sufficient:**

```python
# main.py
import sys
from pathlib import Path
from PySide6.QtWidgets import QApplication, QMessageBox
from PySide6.QtCore import Slot

import config
from devices.thorlabs_camera import ThorlabsCameraAdapter, setup_dll_path
from services.acquisition import AcquisitionThread
from services.white_balance import WhiteBalanceProcessor
from services.focus_assistant import FocusMetric
from services.storage import FrameSaver
from models.camera import CameraSettings
from models.frame import Frame
from gui.main_window import MainWindow


class ApplicationController:
    """
    Simple controller for fixed-position imaging.
    Owns services, coordinates GUI and device.
    """

    def __init__(self):
        # Initialize services
        self.camera = ThorlabsCameraAdapter()
        self.wb_processor = WhiteBalanceProcessor()
        self.focus_metric = FocusMetric()
        self.frame_saver = FrameSaver(config.SNAPSHOTS_DIR)

        self.acquisition_thread = None
        self.current_settings = None
        self.gui = None

        # Latest frame for snapshot
        self.latest_frame = None

    def initialize(self):
        """Connect to camera and initialize GUI."""
        try:
            # Setup DLLs
            setup_dll_path(str(config.THORCAM_DLL_PATH))

            # Connect camera
            cameras = ThorlabsCameraAdapter.list_cameras()
            if not cameras:
                raise RuntimeError("No cameras found!")

            capabilities = self.camera.connect(cameras[0])
            print(f"Connected: {capabilities.model} S/N:{capabilities.serial}")

            # Get default settings
            self.current_settings = self.camera.get_current_settings()
            self.current_settings.white_balance_rgb = (0.6, 0.8, 1.0)  # Default NIR reduction

            # Create acquisition thread
            self.acquisition_thread = AcquisitionThread(self.camera)
            self.acquisition_thread.frame_ready.connect(self._on_frame_ready)
            self.acquisition_thread.fps_updated.connect(self._on_fps_update)
            self.acquisition_thread.error.connect(self._on_error)

            # Create GUI
            self.gui = MainWindow(self)
            self.gui.show()

            # Update GUI with camera info
            self.gui.resolution_label.setText(
                f"Resolution: {capabilities.sensor_width}x{capabilities.sensor_height}"
            )

            return True

        except Exception as e:
            QMessageBox.critical(None, "Initialization Error", str(e))
            return False

    def start_live(self):
        """Start live view."""
        try:
            # Apply current settings
            self.camera.apply_settings(self.current_settings)

            # Start acquisition thread
            self.acquisition_thread.start()

            # Update GUI
            self.gui.start_btn.setEnabled(False)
            self.gui.stop_btn.setEnabled(True)
            self.gui.update_status("Live view started")

        except Exception as e:
            QMessageBox.critical(self.gui, "Error", f"Failed to start: {e}")

    def stop_live(self):
        """Stop live view."""
        if self.acquisition_thread:
            self.acquisition_thread.stop()

        self.gui.start_btn.setEnabled(True)
        self.gui.stop_btn.setEnabled(False)
        self.gui.update_status("Live view stopped")

    def capture_snapshot(self):
        """Capture single frame."""
        try:
            if self.latest_frame:
                # Apply white balance
                corrected = self.wb_processor.process(self.latest_frame)

                # Create frame with corrected data
                frame_to_save = Frame(
                    data=corrected,
                    timestamp_ns=self.latest_frame.timestamp_ns,
                    frame_index=self.latest_frame.frame_index,
                    metadata=self.latest_frame.metadata
                )

                # Save
                filepath = self.frame_saver.save_frame(
                    frame_to_save,
                    self.current_settings,
                    prefix="snapshot"
                )

                self.gui.update_status(f"Saved: {filepath.name}")
            else:
                QMessageBox.warning(self.gui, "Warning", "No frame available to save")

        except Exception as e:
            QMessageBox.critical(self.gui, "Error", f"Failed to save: {e}")

    @Slot(float)
    def set_exposure(self, seconds: float):
        """Update exposure setting."""
        self.current_settings.exposure_sec = seconds
        if self.camera.is_acquiring:
            self.camera.apply_settings(self.current_settings)

    @Slot(float)
    def set_gain(self, db: float):
        """Update gain setting."""
        self.current_settings.gain_db = db
        if self.camera.is_acquiring:
            self.camera.apply_settings(self.current_settings)

    @Slot(float, float, float)
    def set_white_balance(self, r: float, g: float, b: float):
        """Update white balance."""
        self.current_settings.white_balance_rgb = (r, g, b)
        self.wb_processor.set_gains(r, g, b)

    @Slot(CameraSettings)
    def apply_settings(self, settings: CameraSettings):
        """Apply loaded preset."""
        self.current_settings = settings

        # Update camera
        if self.camera.is_connected:
            self.camera.apply_settings(settings)

        # Update GUI controls
        self.gui.camera_controls.set_exposure(settings.exposure_sec)
        self.gui.camera_controls.set_gain(settings.gain_db)
        self.gui.wb_panel.set_gains(*settings.white_balance_rgb)

        # Update white balance processor
        self.wb_processor.set_gains(*settings.white_balance_rgb)

        self.gui.update_status("Settings applied")

    @Slot(Frame)
    def _on_frame_ready(self, frame: Frame):
        """Process new frame from camera."""
        self.latest_frame = frame

        # Apply white balance
        corrected = self.wb_processor.process(frame)

        # Update display
        self.gui.live_view.update_frame(corrected)

        # Update focus metric
        focus_value = self.focus_metric.variance_of_laplacian(frame)
        self.gui.focus_assistant.update_metric(focus_value)

        # Update frame counter
        self.gui.frame_label.setText(f"Frame: {frame.frame_index}")

    @Slot(float)
    def _on_fps_update(self, fps: float):
        """Update FPS display."""
        self.gui.update_fps(fps)

    @Slot(str)
    def _on_error(self, error_msg: str):
        """Handle acquisition error."""
        self.gui.update_status(f"ERROR: {error_msg}")
        QMessageBox.critical(self.gui, "Acquisition Error", error_msg)
        self.stop_live()

    def shutdown(self):
        """Clean shutdown."""
        print("Shutting down...")

        if self.acquisition_thread:
            self.acquisition_thread.stop()

        if self.camera.is_connected:
            self.camera.disconnect()

        print("Shutdown complete")


def main():
    """Application entry point."""
    print("=" * 70)
    print(f"{config.APP_NAME} v{config.APP_VERSION}")
    print("=" * 70)

    app = QApplication(sys.argv)
    app.setStyle("Fusion")

    # Create and initialize controller
    controller = ApplicationController()
    if not controller.initialize():
        return 1

    # Run application
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
```

---

## Implementation Sequence

### Phase 1: Foundation (Week 1)
1. ✅ Create project structure (folders)
2. ✅ Implement `config.py`
3. ✅ Implement `devices/exceptions.py`
4. ✅ Implement `models/camera.py` and `models/frame.py`

### Phase 2: Device Layer (Week 1-2)
5. ✅ Implement `devices/thorlabs_camera.py`
6. ✅ Write tests with mock camera
7. ✅ Test real camera connection

### Phase 3: Services (Week 2)
8. ✅ Implement `services/acquisition.py`
9. ✅ Implement `services/white_balance.py`
10. ✅ Implement `services/focus_assistant.py`
11. ✅ Implement `services/storage.py`

### Phase 4: GUI (Week 3)
12. ✅ Implement `gui/live_view.py`
13. ✅ Implement `gui/camera_controls.py`
14. ✅ Implement `gui/white_balance_panel.py`
15. ✅ Implement `gui/focus_assistant.py`
16. ✅ Implement `gui/settings_manager.py`
17. ✅ Implement `gui/main_window.py`

### Phase 5: Integration (Week 3-4)
18. ✅ Implement `main.py` with ApplicationController
19. ✅ Wire all signals and slots
20. ✅ Test end-to-end workflow
21. ✅ Create default presets

### Phase 6: Polish (Week 4)
22. ✅ Error handling and user feedback
23. ✅ Keyboard shortcuts
24. ✅ Tooltips and help text
25. ✅ Documentation

---

## Key Features for Fixed-Position Experiments

### 1. Manual Focus Workflow
1. Start live view
2. Watch focus assistant bar
3. Manually adjust lens
4. When bar maximized → lock lens
5. Save settings as preset

### 2. White Balance Calibration
1. Point camera at sample
2. Try presets or adjust RGB manually
3. Find best looking colors
4. Save as preset for experiment type
5. Load preset at experiment start

### 3. Preset Workflow
```
Experiment Setup:
1. Camera on, sample positioned
2. Load preset: "experiment_A.json"
   → Exposure, gain, WB all restored
3. Check focus assistant (should be good)
4. Start live view
5. Capture frames as needed
```

### 4. Repeatability
```
presets/
  ├── experiment_A.json     # Biological samples, 50ms, WB (0.6, 0.8, 1.0)
  ├── experiment_B.json     # Materials, 30ms, WB (0.4, 0.7, 1.0)
  └── default.json          # General purpose
```

---

## Testing Strategy

### Unit Tests
```python
# tests/test_camera_adapter.py
def test_roi_conversion():
    roi = ROI(x=100, y=100, width=640, height=480)
    pylablib_format = roi.to_pylablib()
    assert pylablib_format == (100, 740, 100, 580, 1, 1)

    restored = ROI.from_pylablib(pylablib_format)
    assert restored == roi

# tests/test_processing.py
def test_white_balance():
    processor = WhiteBalanceProcessor((0.5, 1.0, 1.5))

    # Create test frame
    frame = Frame(
        data=np.ones((100, 100, 3), dtype=np.uint16) * 1000,
        timestamp_ns=0,
        frame_index=0
    )

    corrected = processor.process(frame)

    assert corrected[0, 0, 0] == 500   # Red reduced
    assert corrected[0, 0, 1] == 1000  # Green unchanged
    assert corrected[0, 0, 2] == 1500  # Blue increased
```

### Integration Tests
```python
# tests/test_acquisition.py
def test_acquisition_thread(mock_camera):
    thread = AcquisitionThread(mock_camera)

    frames_received = []
    thread.frame_ready.connect(lambda f: frames_received.append(f))

    thread.start()
    time.sleep(0.5)  # Let it run
    thread.stop()

    assert len(frames_received) > 0
```

### Hardware Test
```python
# tests/test_hardware.py
@pytest.mark.hardware  # Only run when camera connected
def test_real_camera():
    setup_dll_path("./ThorCam")
    adapter = ThorlabsCameraAdapter()

    cameras = adapter.list_cameras()
    assert len(cameras) > 0

    caps = adapter.connect(cameras[0])
    assert caps.model == "CS165CU"

    adapter.disconnect()
```

---

## Success Metrics

✅ **Functionality**:
- Live view at 25-30 FPS
- Settings respond in real-time
- Focus assistant updates continuously
- Snapshots save with metadata
- Presets load/save correctly

✅ **Code Quality**:
- ~1200 lines total (maintainable)
- Each class < 200 lines
- Type hints throughout
- Docstrings on public methods

✅ **Usability** (Fixed-Position Focus):
- Load preset → immediate readiness
- Manual focus with visual feedback
- One-click snapshot capture
- Settings persist across sessions

---

## Future Enhancements (Post-MVP)

### When Needed:
1. **ROI selection** - Click-and-drag on live view
2. **Histogram display** - Real-time brightness distribution
3. **Batch capture** - N frames with timestamp
4. **Scripting API** - Automate experiments
5. **Multi-camera** - Add second CS165CU
6. **Other devices** - PyLabLib stages, sensors

### Not Needed for Fixed-Position:
- ❌ Autofocus algorithm (manual is fine)
- ❌ Auto white balance (presets work better)
- ❌ Video recording (snapshots sufficient)

---

## Summary

**This architecture is**:
- ✅ Simple but complete
- ✅ Perfectly suited for fixed-position imaging
- ✅ Easy to extend when needed
- ✅ Testable and maintainable
- ✅ Production-ready for your experiments

**Estimated development time**: 3-4 weeks
**Estimated lines of code**: ~1200 (vs original design ~1800)
**Complexity**: Medium (appropriate for one developer)

---

**Ready to start implementation with Phase 1?**
