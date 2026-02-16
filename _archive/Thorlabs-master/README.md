# Thorlabs CS165CU Camera Control Application

Python-based camera control and imaging application for Thorlabs scientific cameras.

**Status**: Phase 6 Complete - Ready for Validation
**Camera**: CS165CU Color Camera (Zelux Series)
**Stack**: PyLabLib + PySide6 + Qt6

---

## Features

- Live camera preview (25-30 FPS)
- Exposure and gain control
- White balance presets (NIR compensation)
- Manual focus assistant (sharpness meter)
- Snapshot capture with metadata
- Settings presets for repeatable experiments
- Real-time FPS and status display

---

## Prerequisites

### Hardware
- Thorlabs CS165CU camera (or compatible Zelux/Kiralux)
- USB 3.0 connection recommended
- Windows 10/11 (64-bit)

### Software
- Python 3.11+ (developed with 3.13)
- ThorCam software (for drivers and DLLs)

---

## Installation

### 1. Clone Repository
```bash
git clone https://github.com/yourusername/thorlabs-camera-control.git
cd thorlabs-camera-control
```

### 2. Create Virtual Environment
```bash
python -m venv .venv
.venv\Scripts\activate  # On Windows
```

### 3. Install Dependencies
```bash
pip install -r requirements.txt
```

### 4. Verify Camera Connection
```bash
python scripts/check_camera.py
```

Expected output:
```
[OK] Camera SDK initialized successfully
[OK] Found 1 camera(s)
[OK] Model: CS165CU (S/N: 33021)
```

---

## Quick Start

### Run Demo Application
```bash
python scripts/demo_white_balance.py
```

### Run Main Application (Phase 1+)
```bash
python src/main.py
```

---

## Project Structure

```
Thorlabs/
├── src/              # Application source code
│   ├── devices/      # Camera adapter
│   ├── models/       # Data models
│   ├── services/     # Business logic
│   └── gui/          # PySide6 interface
├── tests/            # Test suite
├── scripts/          # Utility scripts and demos
├── vendor/           # Third-party vendor files
├── data/             # Runtime data (presets, snapshots)
└── docs/             # Documentation
```

See [Architecture](docs/architecture/ARCHITECTURE.md) for detailed design.

---

## Documentation

### User Guides
- **[Installation Guide](docs/setup/installation.md)** - Setup instructions
- **[Keyboard Shortcuts](docs/guides/keyboard_shortcuts.md)** - Quick reference for hotkeys
- **[Troubleshooting](docs/guides/troubleshooting.md)** - Common issues and solutions
- **[User Manual](docs/guides/demo_instructions.md)** - How to use demos
- **[Color Camera Behavior](docs/guides/color_camera_behavior.md)** - NIR sensitivity

### Developer Documentation
- **[Architecture](docs/architecture/ARCHITECTURE.md)** - System design
- **[Tooltips Reference](docs/guides/tooltips_reference.md)** - UI help text guide
- **[SDK Decision](docs/decisions/sdk_choice.md)** - Why PyLabLib
- **[Changelog](CHANGELOG.md)** - Version history

---

## Development Status

- [x] Phase 0: Project setup and cleanup
- [x] Phase 1: Foundation (models, config)
- [x] Phase 2: Device layer (camera adapter)
- [x] Phase 3: Services (acquisition, processing)
- [x] Phase 4: GUI (PySide6 interface)
- [x] Phase 5: Integration and testing
- [x] Phase 6: Polish and documentation

---

## Technology Stack

| Component | Technology | Version |
|-----------|-----------|---------|
| Language | Python | 3.13 |
| Camera SDK | PyLabLib | 1.4.4 |
| GUI Framework | PySide6 | 6.10.0 |
| Image Processing | NumPy, OpenCV | Latest |
| Vendor SDK | Thorlabs TSI | 0.0.8 |

---

## Key Design Decisions

**PyLabLib over Raw SDK**
- Automatic RGB color conversion
- 75% less boilerplate code
- Multi-device support
- Same stability (identical DLLs)

**PySide6 over PyQt5**
- LGPL license (commercial-friendly)
- Official Qt binding
- Python 3.13 compatible

**Manual Calibration**
- Fixed-position experiments
- Manual focus and white balance more efficient
- Preset system for repeatability

---

## NIR Camera Behavior

The CS165CU is sensitive to 350-1100nm including near-infrared (NIR):
- Human skin reflects ~50% NIR → appears pink/magenta
- LCD screens emit <5% NIR → normal colors
- This is NOT a bug - scientific cameras deliberately lack IR cut filters

**Solutions:**
- Hardware: IR cut filter (~$20-30)
- Software: White balance presets (built into demo)

See [Color Camera Explanation](docs/guides/color_camera_behavior.md) for technical details.

---

## Contributing

This is a research project for fixed-position scientific imaging experiments.
Contributions welcome after Phase 1 completion.

---

## License

[Specify License - MIT/Apache/Proprietary]

---

## Acknowledgments

- Thorlabs Inc. for camera hardware and SDK
- PyLabLib developers for unified device API
- Qt/PySide6 for professional GUI framework
