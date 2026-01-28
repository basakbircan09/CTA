# Thorlabs CS165CU Camera Setup - Complete

**Date**: 2025-11-04
**Camera Model**: CS165CU (Color Camera, Serial: 33021)
**Status**: ✅ All prerequisites installed and tested

---

## ✅ Completed Setup Tasks

### 1. Native DLL Installation
**Location**: `Python Toolkit/dlls/64_lib/`

Copied essential DLLs from ThorCam installation:
- `thorlabs_tsi_camera_sdk.dll` - Core camera SDK
- `thorlabs_tsi_color_processing.dll` - Color processing
- `thorlabs_tsi_demosaic.dll` - Bayer demosaicing
- `thorlabs_tsi_polarization_processor.dll` - Polarization support
- `thorlabs_tsi_usb_hotplug_monitor.dll` - USB device detection
- `thorlabs_tsi_zelux_camera_device.dll` - Zelux camera driver
- `thorlabs_ccd_tsi_usb.dll` - USB communication

### 2. Python Package Installation

**Core Dependencies**:
```bash
numpy==2.3.4           # Array operations
pillow==12.0.0         # Image processing
tifffile==2025.10.16   # TIFF file handling
```

**Thorlabs SDK**:
```bash
thorlabs_tsi_sdk==0.0.8  # Official Python SDK
```

**GUI Framework**:
```bash
PySide6==6.10.0          # Qt6 for Python (Official binding)
```

### 3. Camera Connection Verified

**Camera Information**:
- Model: CS165CU (Color Camera)
- Serial: 33021
- Sensor: 1440 x 1080 pixels
- Bit Depth: 10-bit
- Sensor Type: BAYER (requires color processing)
- Color Filter Phase: 0 (BAYER_RED)
- Firmware: 66-ITN004385-IMG v0.9.6
- Connection: USB 2.0

---

## 📦 Installed Packages Summary

| Package | Version | Purpose |
|---------|---------|---------|
| numpy | 2.3.4 | Array operations, image buffers |
| pillow | 12.0.0 | Image I/O and manipulation |
| tifffile | 2025.10.16 | TIFF format support |
| thorlabs_tsi_sdk | 0.0.8 | Camera SDK wrapper |
| PySide6 | 6.10.0 | GUI framework (Qt6) |
| setuptools | 80.9.0 | Package management |
| wheel | 0.45.1 | Package building |

---

## 🎯 GUI Framework Choice: PySide6

### Why PySide6?

**1. Industry Standard**
- Official Qt for Python (LGPL license - free for commercial use)
- Used by major scientific instrument manufacturers
- 25+ years of Qt development maturity

**2. Performance**
- Native C++ core for minimal overhead
- Hardware-accelerated rendering (OpenGL support)
- Handles real-time 30+ fps camera streams efficiently

**3. Scientific Application Features**
- QGraphicsView for high-performance image display
- QChart for real-time plotting
- Modular architecture (QDockWidget) for multi-device interfaces
- Built-in threading (QThread) for non-blocking camera acquisition
- QtSerialPort for serial device communication

**4. Multi-Device Integration Ready**
Perfect for your comprehensive scientific software:
- Consistent UI across all instrument modules
- Easy to add new device control panels
- Professional appearance and behavior
- Cross-platform (Windows/Linux/macOS)

**5. Longevity**
- Qt 6.x actively developed (released 2020)
- Python 3.13 compatible
- Will remain relevant 10+ years

### Alternatives Considered:
- **PyQt6**: Similar but GPL/Commercial license (expensive)
- **PySide2/PyQt5**: Older Qt 5.x, limited Python 3.13 support
- **Tkinter**: Poor performance, outdated appearance
- **wxPython**: Less powerful, smaller community

---

## 🔧 Camera Specifications

### Physical Sensor
- **Resolution**: 1440 x 1080 pixels
- **Sensor Type**: CMOS with Bayer color filter array
- **Color Pattern**: RGGB (phase 0 = red at origin)
- **Bit Depth**: 10-bit ADC
- **Pixel Size**: Query via `camera.sensor_pixel_width_um`

### Required Processing
Your CS165CU is a **COLOR** camera with Bayer filter:
- Outputs RAW monochrome data with color filter pattern
- **Must** use `MonoToColorProcessor` to convert to RGB
- Color correction matrix required (available from camera)
- White balance matrix required (available from camera)

### Color Processing Workflow
```python
# Initialize color processor
mono_to_color_sdk = MonoToColorProcessorSDK()
processor = mono_to_color_sdk.create_mono_to_color_processor(
    camera.camera_sensor_type,           # BAYER
    camera.color_filter_array_phase,     # 0 (RED)
    camera.get_color_correction_matrix(),
    camera.get_default_white_balance_matrix(),
    camera.bit_depth                     # 10
)

# Convert frame to color
color_image = processor.transform_to_24(
    frame.image_buffer,
    image_width,
    image_height
)  # Returns 24-bit RGB (8 bits/channel)
```

---

## 📝 Next Steps for Development

### 1. Basic Camera Control Application
Create a PySide6 GUI with:
- Live camera preview
- Exposure control (slider)
- Gain control
- ROI selection
- Trigger mode selection (software/hardware/continuous)
- Image capture and save

### 2. Integration Architecture
Design modular structure for future devices:
```
main_window.py          # Main application window
├── camera_module/      # Camera control panel
│   ├── camera_widget.py
│   ├── camera_controller.py
│   └── image_display.py
├── device_module_2/    # Future device 2
└── device_module_3/    # Future device 3
```

### 3. Key Components to Implement
- **CameraThread**: Background thread for frame acquisition
- **ImageDisplay**: QGraphicsView for high-performance display
- **CameraControls**: Exposure, gain, ROI, trigger controls
- **ImageSaver**: TIFF/PNG save with metadata
- **SettingsManager**: Persistent configuration (QSettings)

---

## 🔗 Important File Locations

### Python SDK Source
`Python Toolkit/source/` - Raw Python source files

### Example Scripts
`Python Toolkit/examples/`
- `color_example.py` - Color processing demonstration
- `tkinter_camera_live_view.py` - Live view example (Tkinter)
- `polling_example.py` - Basic frame polling
- `tifffile_tiff_writing_example.py` - Save TIFF files

### Documentation
`docs/Thorlabs_Camera_Python_API_Reference.md` - Complete API reference

### DLL Location
`Python Toolkit/dlls/64_lib/` - Native libraries (now populated)

---

## 🚀 Test Script

Created: `test_camera_connection.py`

Run anytime to verify camera connectivity:
```bash
python test_camera_connection.py
```

---

## 📚 Key API Concepts

### SDK Initialization
```python
with TLCameraSDK() as sdk:
    cameras = sdk.discover_available_cameras()
    with sdk.open_camera(cameras[0]) as camera:
        # Use camera
        pass
```
**Critical**: Always use context managers or call `dispose()` manually

### Camera Workflow
```python
1. Configure: camera.exposure_time_us = 50000
2. Arm: camera.arm(2)  # 2-frame buffer
3. Trigger: camera.issue_software_trigger()
4. Poll: frame = camera.get_pending_frame_or_null()
5. Process: color_image = processor.transform_to_24(...)
6. Disarm: camera.disarm()
```

### Trigger Modes
- **Continuous**: `frames_per_trigger_zero_for_unlimited = 0`
- **Single Shot**: `frames_per_trigger_zero_for_unlimited = 1`
- **Hardware**: `operation_mode = OPERATION_MODE.HARDWARE_TRIGGERED`

---

## ⚠️ Common Pitfalls

1. **Forgetting to dispose**: Causes crashes on exit
2. **Setting ROI while armed**: Not allowed, disarm first
3. **Not using color processing**: CS165CU outputs RAW Bayer data
4. **Blocking UI thread**: Always acquire frames in background thread
5. **Missing DLLs**: Ensure PATH includes DLL directory

---

## 🎓 Learning Resources

**Official Examples**: Study `Python Toolkit/examples/tkinter_camera_live_view.py`
- Shows proper threading architecture
- Demonstrates color processing
- Queue-based frame handling

**API Reference**: `docs/Thorlabs_Camera_Python_API_Reference.md`
- Complete class and method documentation
- Property descriptions
- Enum definitions

**PySide6 Documentation**: https://doc.qt.io/qtforpython-6/
- Comprehensive Qt tutorials
- Widget gallery
- Signal/slot system

---

## ✅ Setup Verification Checklist

- [x] ThorCam software installed
- [x] Native DLLs copied to Python Toolkit
- [x] Python dependencies installed
- [x] thorlabs_tsi_sdk package installed
- [x] PySide6 GUI framework installed
- [x] Camera connected via USB
- [x] Camera detected by Python SDK
- [x] Camera specifications retrieved
- [x] Color processing requirements identified

---

**All prerequisites complete. Ready to begin application development!**
