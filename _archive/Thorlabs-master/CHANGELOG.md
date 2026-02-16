# Changelog

All notable changes to the Thorlabs Camera Control Application will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

---

## [1.0.0] - 2025-11-05

### Summary
First production release. Complete camera control application with live view, manual focus assistant, white balance presets, and settings management.

### Added

#### Core Features
- **Live camera preview** with 25-30 FPS performance
- **Exposure control** (0.1-1000ms) with synchronized spin box and slider
- **Gain control** (0-24dB) for low-light scenarios
- **Snapshot capture** with automatic timestamping and metadata
- **Focus assistant** with real-time sharpness metric
- **White balance presets** including NIR compensation for scientific imaging
- **Settings presets** system for repeatable experiments

#### GUI Components
- Main window with resizable panels (QSplitter-based layout)
- Live view widget with auto-scaling display
- Camera control panel with dual exposure controls
- White balance panel with 6 presets (Default, Reduce NIR, Strong NIR, Warm, Cool, Custom)
- Focus assistant with visual progress bar
- Settings manager for preset save/load/delete
- Status bar with FPS display and operation feedback

#### Keyboard Shortcuts
- **Space**: Toggle live view on/off
- **Ctrl+S**: Capture snapshot
- **Ctrl+H**: Toggle controls panel visibility
- **Ctrl+Q**: Quit application

#### User Experience
- 31 tooltips across all interactive widgets
- Status bar tips for additional context
- Comprehensive error handling with user-friendly dialogs
- Persistent error messages for critical failures
- Re-entrancy guards to prevent error loops

#### Documentation
- Complete architecture documentation (56KB)
- Keyboard shortcuts reference guide
- Tooltips reference guide for maintaiability
- Troubleshooting guide with common issues
- NIR camera behavior explanation
- Demo instructions and usage tips
- SDK decision rationale
- Installation guide

#### Developer Features
- 25 unit tests covering all layers (100% pass rate)
- Mock camera for testing without hardware
- Dependency injection for testability
- Comprehensive logging system (file + console)
- Clean OOP architecture (devices/models/services/gui/app)

### Technical Details

#### Architecture
- **Devices**: ThorlabsCameraAdapter with PyLabLib backend
- **Models**: CameraSettings, Frame (dataclasses)
- **Services**: AcquisitionThread, FocusMetric, WhiteBalanceProcessor, FrameSaver
- **GUI**: PySide6 widgets (Qt6)
- **Controller**: ApplicationController coordinating all layers

#### Dependencies
- Python 3.13
- PyLabLib 1.4.4 (camera SDK abstraction)
- PySide6 6.10.0 (GUI framework)
- NumPy 2.2.1 (image processing)
- OpenCV 4.11 (image I/O and processing)

#### Camera Support
- Thorlabs CS165CU (primary target)
- Compatible with Zelux/Kiralux series

---

## Development Phases

### Phase 0: Project Setup ✅
- Repository structure
- Virtual environment
- Dependency management
- Git configuration

### Phase 1: Foundation ✅
- Data models (Frame, CameraSettings, CameraCapabilities)
- Configuration system
- Project constants

### Phase 2: Device Layer ✅
- ThorlabsCameraAdapter implementation
- PyLabLib integration
- Camera enumeration and connection
- Settings application
- Acquisition lifecycle management

### Phase 3: Services ✅
- AcquisitionThread for background frame capture
- WhiteBalanceProcessor for RGB gain correction
- FocusMetric for manual focus assistance
- FrameSaver for snapshot export (PNG/TIFF)

### Phase 4: GUI ✅
- LiveViewWidget with auto-scaling
- CameraControlPanel with exposure/gain controls
- WhiteBalancePanel with presets
- FocusAssistantWidget
- SettingsManagerWidget
- MainWindow composition

### Phase 5: Integration ✅
- ApplicationController coordination
- Signal/slot wiring
- End-to-end testing
- Hardware validation

### Phase 6: Polish ✅
- Comprehensive error handling
- Keyboard shortcuts
- 31 tooltips + status tips
- Complete documentation
- Troubleshooting guide

---

## Known Issues

### Sporadic Acquisition Errors
- **Frequency**: ~0.1% of frames
- **Cause**: Thorlabs SDK internal timeout
- **Impact**: Single frame drop
- **Status**: Expected behavior, application handles gracefully

### NIR Color Cast
- **Symptom**: Human skin appears pink/magenta
- **Cause**: CS165CU sensitive to 350-1100nm (includes NIR)
- **Solution**: Use "Reduce NIR" or "Strong NIR" white balance preset
- **Status**: Hardware characteristic, not a bug

---

## Future Enhancements

### Planned Features
- **Recording**: Save video sequences to disk
- **Exposure/Gain fine-tuning**: +/- keyboard shortcuts during live view
- **ROI selection**: Region-of-interest for faster acquisition
- **Histogram display**: Real-time exposure analysis
- **Multi-camera support**: Simultaneous control of multiple cameras

### Under Consideration
- **Auto-focus**: Automated lens control (requires motorized lens)
- **Auto-white-balance**: One-click reference image calibration
- **Scripting API**: Python API for automation
- **Plugin system**: User-extensible processing pipeline

---

## Migration Guide

### From Demo Scripts to v1.0.0

**Old approach** (demo_white_balance.py):
```python
# Single monolithic script
from pylablib.devices import Thorlabs
cam = Thorlabs.ThorlabsTLCamera()
```

**New approach** (v1.0.0):
```python
# Run application
python src/app/main.py
```

**Benefits:**
- No code changes required for basic usage
- All features accessible via GUI
- Settings persist via preset system
- Professional error handling

---

## Contributors

- **Development**: GDSandStorm
- **Camera Hardware**: Thorlabs Inc.
- **SDK Support**: PyLabLib developers
- **GUI Framework**: Qt/PySide6 team

---

## License

[Specify License - MIT/Apache/Proprietary]

---

## Acknowledgments

Special thanks to:
- Thorlabs Inc. for robust camera hardware and SDK
- PyLabLib developers for unified device API
- Qt/PySide6 for professional GUI framework
- Python community for excellent scientific computing ecosystem

---

**Version History:**
- **v1.0.0** (2025-11-05): Initial release - Phase 0-6 complete
