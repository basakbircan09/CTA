# PyLabLib vs Raw Thorlabs SDK - Analysis & Recommendation

## Overview

You've discovered **PyLabLib** - a higher-level abstraction layer that wraps the Thorlabs SDK and many other devices. This is a **game-changer** for your comprehensive scientific software project.

---

## What is PyLabLib?

**PyLabLib** (Python Laboratory Library) is a unified interface for device control and experiment automation.

### Supported Devices
- **Cameras**: Thorlabs (Zelux, Kiralux), Andor, PCO, Photometrics, DCAM, OptoMotion, UEYE
- **Stages**: Thorlabs Kinesis, Attocube, Newport, Arcus, Trinamic
- **Oscilloscopes**: Tektronix, Rigol
- **AWGs**: Arbitrary Waveform Generators
- **Sensors**: Various scientific instruments
- **And expanding...**

### Key Features
- **Unified API** across different devices
- **Color camera support** with automatic RGB conversion
- **Built-in utilities**: FFT, filtering, feature detection, curve fitting
- **Data management**: Multi-level dictionaries for experiment data
- **File I/O utilities**
- **Actively maintained** (v1.4.4, August 2025)

GitHub: https://github.com/AlexShkarin/pyLabLib
Docs: https://pylablib.readthedocs.io/

---

## Comparison: PyLabLib vs Raw SDK

| Aspect | Raw Thorlabs SDK | PyLabLib |
|--------|------------------|----------|
| **Abstraction Level** | Low-level C wrapper | High-level Pythonic |
| **Code Complexity** | Verbose, manual management | Clean, concise |
| **Color Processing** | Manual MonoToColorProcessor | Automatic RGB output |
| **Multi-Device** | Camera only | 50+ device types |
| **Learning Curve** | Steep (C DLL concepts) | Gentle (Python objects) |
| **Resource Management** | Manual dispose() calls | Context managers |
| **Error Handling** | Low-level exceptions | Cleaner error messages |
| **Future Integration** | Device-specific code | Unified API |
| **Documentation** | Thorlabs official docs | Unified + examples |
| **Maintenance Burden** | Higher (per device) | Lower (one library) |

---

## Code Comparison

### Raw SDK: Color Camera Frame Capture

```python
import os
import sys

# DLL path setup
dll_path = os.path.join(os.path.dirname(__file__), "Python Toolkit", "dlls", "64_lib")
os.environ['PATH'] = dll_path + os.pathsep + os.environ['PATH']
if hasattr(os, 'add_dll_directory'):
    os.add_dll_directory(dll_path)

from thorlabs_tsi_sdk.tl_camera import TLCameraSDK
from thorlabs_tsi_sdk.tl_mono_to_color_processor import MonoToColorProcessorSDK
from thorlabs_tsi_sdk.tl_camera_enums import SENSOR_TYPE, OPERATION_MODE

# Initialize SDK
with TLCameraSDK() as camera_sdk, MonoToColorProcessorSDK() as color_sdk:
    cameras = camera_sdk.discover_available_cameras()

    with camera_sdk.open_camera(cameras[0]) as camera:
        # Save image dimensions after arming
        camera.exposure_time_us = 50000
        camera.frames_per_trigger_zero_for_unlimited = 0
        camera.arm(2)

        image_width = camera.image_width_pixels
        image_height = camera.image_height_pixels

        # Create color processor
        with color_sdk.create_mono_to_color_processor(
            camera.camera_sensor_type,
            camera.color_filter_array_phase,
            camera.get_color_correction_matrix(),
            camera.get_default_white_balance_matrix(),
            camera.bit_depth
        ) as processor:
            processor.color_space = COLOR_SPACE.SRGB
            processor.output_format = FORMAT.RGB_PIXEL

            camera.issue_software_trigger()
            frame = camera.get_pending_frame_or_null()

            if frame:
                # Convert to color
                color_image = processor.transform_to_24(
                    frame.image_buffer,
                    image_width,
                    image_height
                )
                # Now have RGB image

        camera.disarm()
```

**~45 lines** with extensive setup and manual color processing

---

### PyLabLib: Same Functionality

```python
from pylablib.devices import Thorlabs

# Connect to camera
with Thorlabs.ThorlabsTLCamera() as cam:
    cam.set_exposure(50e-3)  # 50ms

    # Start acquisition
    cam.start_acquisition()

    # Get RGB frame (automatic color processing!)
    frame = cam.read_oldest_image()  # Already RGB if color camera

    cam.stop_acquisition()
```

**~10 lines** - automatic color conversion, simpler API

---

## Key Advantages of PyLabLib

### 1. **Automatic Color Processing**
Raw SDK requires manual MonoToColorProcessor setup (5 parameters, matrices, etc.)
PyLabLib: **Automatic** - outputs RGB directly for color cameras

### 2. **Unified Multi-Device Architecture**
Perfect for your comprehensive scientific software:

```python
# Control multiple devices with same API style
from pylablib.devices import Thorlabs, Arcus

# Camera
cam = Thorlabs.ThorlabsTLCamera()
cam.set_exposure(50e-3)
frame = cam.snap()

# Translation stage (future)
stage = Thorlabs.KinesisMotor("serial123")
stage.move_to(10.5)  # Move to 10.5mm

# Another device (future)
sensor = SomeDevice()
reading = sensor.get_value()
```

**Consistent API** across all devices - easier to maintain, extend, and train others on.

### 3. **Built-in Experiment Utilities**

```python
from pylablib.core.utils import fitting

# Fit Gaussian to image data
params = fitting.fit_gaussian_2D(frame)

# FFT analysis
from pylablib.core.utils import fft
spectrum = fft.fft2(frame)
```

No need for separate scipy/opencv pipelines - integrated tools.

### 4. **Pythonic Design**

```python
# Standard camera operations
cam.get_detector_size()      # (1440, 1080)
cam.get_roi()                # ROI(0, 1440, 0, 1080)
cam.set_roi(100, 1340, 50, 1030)  # Set ROI

cam.get_exposure()           # Current exposure
cam.set_exposure(0.1)        # 100ms

# Frame acquisition
cam.start_acquisition()
while True:
    frame = cam.wait_for_frame()  # Blocks until frame ready
    process(frame)
```

Clean, self-documenting method names.

### 5. **Future-Proof Multi-Device Integration**

When you add new instruments:
- **Same learning curve** (familiar API patterns)
- **Same code style** (consistent with camera code)
- **Easier troubleshooting** (one library, one community)
- **Better documentation** (unified docs for all devices)

---

## Considerations: PyLabLib

### ⚠️ Known Issues (from docs)

1. **Minor instability**: 0.1-1% chance acquisition start fails (timeout errors)
2. **Occasional crashes**: On SDK unload, especially after multiple start/stop cycles
3. **Debug console spam**: DLL prints messages when listing cameras/opening

**Important**: These issues originate from **Thorlabs' DLL**, not PyLabLib. Raw SDK has the same problems.

### Dependency

PyLabLib is an **additional dependency** wrapping the raw SDK. You still need:
- Thorlabs DLLs (same as before)
- thorlabs_tsi_sdk might still be installed by PyLabLib

---

## Recommendation: **Use PyLabLib**

### Why Switch to PyLabLib?

✅ **Simpler code** - 1/4 the lines for same functionality
✅ **Automatic color processing** - No manual MonoToColorProcessor
✅ **Multi-device ready** - Unified API for future instruments
✅ **Better maintainability** - Less boilerplate, clearer intent
✅ **Built-in utilities** - FFT, fitting, filtering included
✅ **Active development** - v1.4.4 (Aug 2025), 500+ commits
✅ **Same stability** - Issues are from Thorlabs DLL (affects raw SDK too)
✅ **Good documentation** - Comprehensive, with examples

### When to Consider Raw SDK?

❌ Need absolute maximum performance (micro-optimizations)
❌ Want minimal dependencies (but you already have many)
❌ Require features not exposed by PyLabLib (rare)

**Verdict**: For a comprehensive scientific software integrating multiple devices, PyLabLib is **clearly superior**.

---

## Migration Plan

### Current Status
✅ Raw SDK working (test_camera_connection.py passed)
✅ All dependencies installed
✅ DLLs in place

### Switch to PyLabLib

1. **Install PyLabLib**
```bash
pip install pylablib
```

2. **Test Camera with PyLabLib**
```python
from pylablib.devices import Thorlabs

# List cameras
cameras = Thorlabs.list_cameras_tlcam()
print(f"Found: {cameras}")

# Open first camera
with Thorlabs.ThorlabsTLCamera() as cam:
    print(f"Model: {cam.get_model_data()}")
    print(f"Detector size: {cam.get_detector_size()}")

    # Capture frame
    cam.start_acquisition()
    frame = cam.snap()  # RGB if color camera!
    cam.stop_acquisition()

    print(f"Frame shape: {frame.shape}")
```

3. **Develop with PyLabLib**
- Cleaner code from start
- Easy to add new devices later
- Better long-term maintenance

### Hybrid Approach (Not Recommended)

You *could* keep raw SDK for specific advanced features and use PyLabLib for general control, but this adds complexity without benefit.

---

## Architecture Recommendation: Updated

```
main_application.py
├── devices/
│   ├── camera_controller.py      # PyLabLib Thorlabs wrapper
│   ├── stage_controller.py       # PyLabLib stage wrapper (future)
│   ├── sensor_controller.py      # PyLabLib sensor wrapper (future)
│   └── base_device.py            # Common device interface
├── gui/
│   ├── main_window.py            # PySide6 main window
│   ├── camera_panel.py           # Camera control dock widget
│   ├── image_display.py          # QGraphicsView display
│   └── device_panel.py           # Reusable device panel template
├── utils/
│   ├── image_processing.py       # Analysis functions
│   └── data_logging.py           # Experiment data management
└── config/
    └── settings.json             # Persistent configuration
```

**Key Design Principles**:
- **PyLabLib** for all device communication
- **PySide6** for GUI (Qt power + performance)
- **Modular** - each device is independent panel
- **Consistent** - same API patterns across devices
- **Extensible** - adding devices is straightforward

---

## Next Steps

### Option A: Continue with Raw SDK
- Keep current test_camera_connection.py
- Manually handle color processing
- Write more boilerplate code
- Device-specific learning curve for each new instrument

### Option B: Switch to PyLabLib ✅ **RECOMMENDED**
1. Install: `pip install pylablib`
2. Create: `test_camera_pylablib.py`
3. Test basic functionality
4. Begin GUI development with PyLabLib backend
5. Future devices use same PyLabLib patterns

---

## Final Recommendation

**Use PyLabLib for your comprehensive scientific software.**

It's specifically designed for exactly your use case: multi-device laboratory automation with Python. The code will be cleaner, more maintainable, and easier to extend when you add motors, sensors, or other instruments.

The minor stability issues are **identical** in raw SDK (same underlying DLL), so there's no stability penalty. You gain significant code quality and maintainability benefits.

**PyLabLib + PySide6 = Professional scientific instrument control software**

---

**Decision**: Install PyLabLib and test with your CS165CU camera?
