# PyLabLib + PySide6 Compatibility - RESOLVED ✅

## Your Concern
> "I want my program's GUI generated with PySide6, instead of other Qt binding that might be here for pylablib."

## Answer: **PyLabLib is GUI-Agnostic** ✅

**PyLabLib does NOT dictate your GUI framework.** It's a device control library, not a GUI framework.

---

## How PyLabLib Works

### Core Architecture (Headless)

PyLabLib is fundamentally a **device control library**:
- Communicates with hardware via USB, serial, VISA, etc.
- Returns data as numpy arrays
- **No GUI dependency required** for device control

```python
from pylablib.devices import Thorlabs

# This works WITHOUT any Qt binding installed
cam = Thorlabs.ThorlabsTLCamera()
cam.start_acquisition()
frame = cam.read_oldest_image()  # Returns numpy array
# No GUI involved - just device control!
```

### Optional GUI Components

PyLabLib *includes* optional GUI utilities (for quick visualization):
- Uses PyQt5/PySide2 (Qt5) for its *own* optional GUI tools
- Includes pyqtgraph for plotting utilities
- **These are OPTIONAL** - only used if you choose to use pylablib's GUI tools

---

## Installation Strategy for Your Project

### Option 1: Lightweight Installation (RECOMMENDED)

Install without GUI dependencies:

```bash
pip install pylablib-lightweight[devio]
```

**Includes**:
- ✅ Device control (cameras, stages, sensors)
- ✅ Basic dependencies (numpy, scipy, pandas)
- ✅ Communication packages (pyserial, pyvisa, pyusb)
- ❌ No PyQt5, no pyqtgraph

Then separately install YOUR choice of GUI:
```bash
pip install PySide6
```

**Result**: Clean separation - PyLabLib for devices, PySide6 for GUI

---

### Option 2: Full Installation (Still Works)

```bash
pip install pylablib
pip install PySide6
```

**Includes**:
- ✅ Everything from Option 1
- ⚠️ PyQt5 (unused, but installed)
- ⚠️ pyqtgraph (unused, but installed)
- ✅ PySide6 (your GUI)

**Result**: Extra packages installed, but no conflict. You simply don't use pylablib's GUI tools.

---

## Your Architecture: PyLabLib Backend + PySide6 Frontend

### Device Layer (PyLabLib - No GUI)

```python
# camera_controller.py
from pylablib.devices import Thorlabs
import numpy as np

class CameraController:
    def __init__(self, serial=None):
        self.cam = Thorlabs.ThorlabsTLCamera(serial=serial)

    def set_exposure(self, time_ms):
        self.cam.set_exposure(time_ms / 1000.0)

    def capture_frame(self):
        """Returns numpy array - no GUI dependency"""
        return self.cam.snap()

    def start_continuous(self):
        self.cam.start_acquisition()

    def get_latest_frame(self):
        """Returns numpy array"""
        return self.cam.read_oldest_image()

    def stop(self):
        self.cam.stop_acquisition()

    def close(self):
        self.cam.close()
```

**Zero GUI code** - pure device control with numpy arrays.

---

### GUI Layer (PySide6)

```python
# camera_widget.py
from PySide6.QtWidgets import QWidget, QVBoxLayout, QLabel, QSlider
from PySide6.QtCore import QTimer, Qt
from PySide6.QtGui import QImage, QPixmap
import numpy as np

from camera_controller import CameraController

class CameraWidget(QWidget):
    def __init__(self):
        super().__init__()
        self.camera = CameraController()

        # PySide6 GUI components
        self.image_label = QLabel()
        self.exposure_slider = QSlider(Qt.Horizontal)

        layout = QVBoxLayout()
        layout.addWidget(self.image_label)
        layout.addWidget(self.exposure_slider)
        self.setLayout(layout)

        # Timer for frame updates
        self.timer = QTimer()
        self.timer.timeout.connect(self.update_frame)
        self.timer.start(33)  # 30 fps

        self.camera.start_continuous()

    def update_frame(self):
        # Get frame from PyLabLib (numpy array)
        frame = self.camera.get_latest_frame()

        # Convert numpy to PySide6 QImage
        if frame is not None:
            qimage = self.numpy_to_qimage(frame)
            pixmap = QPixmap.fromImage(qimage)
            self.image_label.setPixmap(pixmap)

    def numpy_to_qimage(self, array):
        """Convert numpy array to QImage (PySide6)"""
        if array.ndim == 2:  # Grayscale
            height, width = array.shape
            bytes_per_line = width
            return QImage(array.data, width, height, bytes_per_line, QImage.Format_Grayscale8)
        elif array.ndim == 3:  # RGB
            height, width, channels = array.shape
            bytes_per_line = width * channels
            return QImage(array.data, width, height, bytes_per_line, QImage.Format_RGB888)

    def closeEvent(self, event):
        self.camera.stop()
        self.camera.close()
        event.accept()
```

**Pure PySide6** - no PyQt5 contamination.

---

## Key Points

### 1. **PyLabLib is Qt-Agnostic**
- Device control layer has **zero Qt dependency**
- Returns numpy arrays (universal format)
- Works with any GUI framework: PySide6, PyQt6, Tkinter, Kivy, etc.

### 2. **PyQt5 Dependency is for PyLabLib's Own Tools**
If you install full `pylablib`, it includes PyQt5 for its optional GUI utilities:
- `pylablib.aux_libs.gui` - Optional GUI helpers
- Built-in plotting/visualization widgets

**You don't have to use these.** They're helpers, not requirements.

### 3. **No Runtime Conflicts**
Having both PyQt5 (from pylablib) and PySide6 (your choice) installed:
- ✅ **No conflicts** - they're separate packages
- ✅ **No interference** - you explicitly import what you use
- ✅ **No mixing** - your code uses PySide6 exclusively

```python
# Your code only imports PySide6
from PySide6.QtWidgets import QApplication  # ✅ Your GUI
from pylablib.devices import Thorlabs        # ✅ Device control (no GUI)

# PyQt5 is installed but never imported - no conflict
```

### 4. **Lightweight Option Eliminates Concern Entirely**
```bash
pip install pylablib-lightweight[devio]  # No PyQt5 at all
pip install PySide6                      # Your GUI
```

This is the **cleanest** approach - only installs what you need.

---

## Recommendation

### For Your Project: Use Option 1 (Lightweight)

**Install**:
```bash
pip install pylablib-lightweight[devio]
pip install PySide6
```

**Advantages**:
✅ No unnecessary dependencies (no PyQt5, no pyqtgraph)
✅ Smaller virtual environment
✅ Faster installation
✅ Crystal clear separation: PyLabLib = devices, PySide6 = GUI
✅ Full device control capabilities
✅ 100% compatible with PySide6

**You get**:
- All PyLabLib device drivers (cameras, stages, etc.)
- Communication libraries (serial, VISA, USB)
- Core utilities (numpy, scipy, pandas)
- Your GUI framework of choice (PySide6)

---

## Verification Test

After installation, verify no conflicts:

```python
# test_no_qt_conflict.py
import sys

# 1. Test PyLabLib device control (no GUI)
from pylablib.devices import Thorlabs
print("✓ PyLabLib imported (device control)")

cameras = Thorlabs.list_cameras_tlcam()
print(f"✓ Found {len(cameras)} camera(s)")

# 2. Test PySide6 import (your GUI)
from PySide6.QtWidgets import QApplication, QLabel
from PySide6.QtCore import QTimer
print("✓ PySide6 imported successfully")

# 3. Verify Qt version
from PySide6.QtCore import qVersion
print(f"✓ Qt version: {qVersion()}")

# 4. Check no PyQt5 in your imports
assert 'PyQt5' not in sys.modules
print("✓ PyQt5 not in loaded modules")

print("\n✅ All clear! PyLabLib + PySide6 working perfectly.")
```

---

## Summary

**Your concern is RESOLVED** ✅

- **PyLabLib does NOT force PyQt5 on your GUI**
- **Device control is GUI-independent** (returns numpy arrays)
- **Install lightweight version** to avoid PyQt5 entirely
- **PySide6 and PyLabLib work together perfectly**
- **No conflicts, no contamination, no mixing**

**Architecture**:
```
Your Application
├── Device Layer: PyLabLib (headless, numpy arrays)
└── GUI Layer: PySide6 (100% your choice)
```

**Clean separation, zero conflicts, professional architecture.**

---

## Next Step

Install the lightweight version and test with your camera:

```bash
pip install pylablib-lightweight[devio]
```

Create test script to verify PySide6 compatibility?
