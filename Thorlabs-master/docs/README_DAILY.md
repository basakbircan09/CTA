# Daily Session Initialization

**Purpose:** Standard checklist for starting each coding session.

**Project Status:** Phase 6 Complete - Production Ready (v1.0.0)

---

## Quick Start

### 1. Environment Setup
```powershell
cd C:\Users\go97mop\PycharmProjects\Thorlabs
.\.venv\Scripts\activate
```

### 2. System Health Check
```powershell
# Verify Python environment
python --version  # Expected: 3.13+

# Run test suite (should complete in ~10s)
pytest tests/ -v  # Expected: 25/25 passing

# Check camera connection (optional, requires hardware)
python scripts\check_camera.py
```

**Expected test output:**
```
========================= 25 passed, 1 warning in ~8s =========================
```

### 3. Launch Application
```powershell
# Run main application
python src\app\main.py

# Or run specific demos
python scripts\demo_white_balance.py
```

---

## Project Overview

### Current Phase
- **Status:** Phase 6 Complete (Polish & Documentation)
- **Version:** 1.0.0
- **All features:** Implemented and validated
- **All tests:** 25/25 passing
- **All docs:** Complete

### What's Working
- ✅ Live camera preview (25-30 FPS)
- ✅ Exposure and gain control
- ✅ White balance presets (6 presets including NIR compensation)
- ✅ Focus assistant with real-time sharpness metric
- ✅ Snapshot capture with automatic timestamping
- ✅ Settings presets (save/load/delete)
- ✅ Keyboard shortcuts (Space, Ctrl+S, Ctrl+H, Ctrl+Q)
- ✅ 31 tooltips across all UI controls
- ✅ Comprehensive error handling with logging

---

## Architecture Quick Reference

```
Thorlabs/
├── src/                      # Application source code
│   ├── app/                  # Main entry point and controller
│   │   ├── main.py           # Application entry (run this)
│   │   └── controller.py     # ApplicationController (coordinates all layers)
│   ├── devices/              # Hardware abstraction
│   │   └── thorlabs_camera.py  # ThorlabsCameraAdapter (PyLabLib wrapper)
│   ├── models/               # Data models
│   │   ├── camera.py         # CameraSettings, CameraCapabilities
│   │   └── frame.py          # Frame dataclass
│   ├── services/             # Business logic
│   │   ├── acquisition.py    # AcquisitionThread (background frame capture)
│   │   ├── white_balance.py  # WhiteBalanceProcessor
│   │   ├── focus_assistant.py # FocusMetric
│   │   └── storage.py        # FrameSaver (PNG/TIFF export)
│   └── gui/                  # PySide6 widgets
│       ├── main_window.py    # MainWindow (QSplitter layout)
│       ├── camera_controls.py # Exposure/gain controls
│       ├── white_balance_panel.py # WB presets
│       ├── focus_assistant.py # Focus score display
│       ├── live_view.py      # Image display
│       └── settings_manager.py # Preset management
├── tests/                    # Unit tests (25 tests)
│   ├── unit/                 # All layer tests
│   └── fixtures/             # Mock camera for testing
├── docs/                     # Documentation
│   ├── architecture/         # ARCHITECTURE.md (design doc)
│   ├── guides/               # User guides (keyboard shortcuts, troubleshooting, etc.)
│   ├── decisions/            # SDK choice rationale
│   ├── testing/              # Test protocols
│   └── VALIDATION_CHECKLIST.md # DoD validation (150+ items)
├── scripts/                  # Utility scripts
│   ├── check_camera.py       # Hardware diagnostic
│   └── demo_*.py             # Demo scripts
├── data/                     # Runtime data (gitignored)
│   ├── presets/              # Saved settings (JSON)
│   └── snapshots/            # Captured images (PNG)
├── logs/                     # Application logs (gitignored)
├── config.py                 # Configuration constants
├── requirements.txt          # Python dependencies
├── CHANGELOG.md              # Version history
└── README.md                 # Project overview
```

---

## Key Documentation

### Essential Reading
1. **[ARCHITECTURE.md](architecture/ARCHITECTURE.md)** - Complete system design (56KB)
2. **[VALIDATION_CHECKLIST.md](VALIDATION_CHECKLIST.md)** - DoD validation guide (150+ items)
3. **[CHANGELOG.md](../CHANGELOG.md)** - Version history (what's changed)

### User Guides
- **[keyboard_shortcuts.md](guides/keyboard_shortcuts.md)** - Keyboard shortcuts reference
- **[troubleshooting.md](guides/troubleshooting.md)** - Common issues and solutions
- **[tooltips_reference.md](guides/tooltips_reference.md)** - UI help text catalog
- **[color_camera_behavior.md](guides/color_camera_behavior.md)** - NIR sensitivity explanation

### Testing Protocols
- **[GUI_SMOKE_TEST.md](testing/GUI_SMOKE_TEST.md)** - Manual GUI validation
- **[HARDWARE_TEST.md](testing/HARDWARE_TEST.md)** - Hardware validation protocol

---

## Common Tasks

### Running Tests
```powershell
# All tests
pytest tests/ -v

# Specific test file
pytest tests/unit/test_app_controller.py -v

# With coverage (optional)
pytest tests/ --cov=src --cov-report=html
```

### Checking Logs
```powershell
# View latest log
ls logs/ | sort | tail -1 | xargs cat

# Monitor live
Get-Content logs\app_*.log -Wait -Tail 20
```

### Managing Presets
```powershell
# List saved presets
ls data\presets\

# View preset JSON
cat data\presets\my_preset.json
```

### Capturing Snapshots
```powershell
# Launch app, start live view (Space), capture (Ctrl+S)
# Snapshots saved to: data\snapshots\snapshot_YYYYMMDD_HHMMSS.png
ls data\snapshots\
```

---

## Development Guidelines

### Before Starting Work
1. **Pull latest changes** (if working with version control)
2. **Run test suite** - Ensure baseline health
3. **Review open TODOs** - Check docs/notes/ for pending items
4. **Check logs** - Review any errors from previous session

### During Development
1. **Run tests frequently** - After each significant change
2. **Check logs** - Monitor logs/ directory for errors
3. **Update docs** - Keep documentation in sync with code changes
4. **Use tooltips reference** - Maintain UI help text consistency

### Before Committing
1. **Run full test suite** - All 25 tests must pass
2. **Check git status** - No unintended files staged
3. **Review changes** - Verify code quality and style
4. **Update CHANGELOG.md** - Document significant changes
5. **Clean temporary files** - Run cleanup if needed

---

## Troubleshooting Session Startup

### Camera Not Found
```powershell
# 1. Check camera connection
python scripts\check_camera.py

# 2. Verify ThorCam works
# Open ThorCam application, confirm camera appears

# 3. Check DLL path
echo $env:PATH  # Should include ThorCam directory
```

### Test Failures
```powershell
# 1. Check virtual environment
pip list | grep -E "(pylablib|PySide6|pytest)"

# 2. Reinstall dependencies
pip install -r requirements.txt --force-reinstall

# 3. Clear cache
rm -rf __pycache__ .pytest_cache
pytest tests/ -v --cache-clear
```

### Import Errors
```powershell
# 1. Verify PYTHONPATH (usually not needed)
echo $env:PYTHONPATH

# 2. Check directory structure
ls src/  # Should see: app, devices, gui, models, services

# 3. Reinstall in development mode (if needed)
pip install -e .
```

---

## Next Steps (Future Enhancements)

### Potential Features
- Video recording (save sequences to disk)
- ROI selection for faster acquisition
- Histogram display for exposure analysis
- Multi-camera simultaneous control
- Auto-focus (requires motorized lens)
- Scripting API for automation

### Technical Debt
- None identified (Phase 6 complete)

### Known Issues
1. **Sporadic acquisition errors** (~0.1% of frames)
   - Cause: Thorlabs SDK internal timeout
   - Status: Expected behavior, handled gracefully

2. **NIR color cast on skin tones**
   - Cause: CS165CU sensitive to 350-1100nm
   - Solution: Use "Reduce NIR" or "Strong NIR" preset
   - Status: Hardware characteristic, not a bug

---

## Session Close-out

### Before Ending Session
1. **Stop live view** - Press Space or click Stop
2. **Close application** - Ctrl+Q or close window
3. **Commit changes** - If work is complete
4. **Update notes** - Record findings in docs/notes/ (if needed)
5. **Deactivate environment** - `deactivate`

### Clean Exit
```powershell
# Camera disconnects automatically on application close
# No manual cleanup required
```

---

## Quick Commands Reference

```powershell
# Activate environment
.\.venv\Scripts\activate

# Run tests
pytest tests/ -v

# Run application
python src\app\main.py

# Check camera
python scripts\check_camera.py

# View logs
ls logs\ | sort | tail -1 | xargs cat

# Deactivate
deactivate
```

---

**Last Updated:** Phase 6 completion (v1.0.0, 2025-11-05)

**Status:** Production ready, all features complete, 25/25 tests passing ✅
