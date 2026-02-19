# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

CTA (Camera, Thorlabs & Automation) is a Python 3.13 / PySide6 desktop application for automated electrochemistry sample-array processing. It integrates a Thorlabs CS165CU scientific camera and a PI three-axis XYZ translation stage (3x C-863 Mercury controllers). Designed as a subsystem for the GOED (General Orchestrator for Electrochemistry Devices) platform.

## Commands

```bash
# Run the application (requires real hardware)
python main.py

# Run all tests (123 tests, no hardware needed)
pytest device_drivers/PI_Control_System/tests/ -v

# Run a single test module
pytest device_drivers/PI_Control_System/tests/test_motion_service.py -v

# Run tests with coverage
pytest --cov=device_drivers device_drivers/PI_Control_System/tests/

# PI stage configuration CLI
python -m device_drivers.PI_Control_System.config show
python -m device_drivers.PI_Control_System.config set --park-position X=200.0 Y=200.0 Z=200.0
```

## Architecture

### Entry Point & GUI Layer
- `main.py` — Sets up DLL paths, launches `SimpleStageApp(use_mock=False)`
- `gui/app_window.py` — Main orchestrator window (~460 lines). Wires all widgets and services, implements workflow handlers (connect, initialize, capture, detect, adjust)
- `gui/widgets/` — Toolbar, CameraSettings, StageControl, ImageViewer, LogPanel

### PI Control System (`device_drivers/PI_Control_System/`)
Self-contained modular subsystem with layered architecture:

- **Core models** (`core/models.py`) — Immutable frozen dataclasses: `Axis`, `Position`, `ConnectionState`, `InitializationState`
- **Hardware abstraction** (`core/hardware/interfaces.py`) — `AxisController` ABC enables real/mock swapping
- **Hardware implementations** — `PIAxisController` (real pipython), `MockAxisController` (deterministic testing)
- **PIControllerManager** (`hardware/pi_manager.py`) — Coordinates 3 axes, enforces safe reference order (Z→X→Y)
- **Services** — `EventBus` (thread-safe pub/sub), `ConnectionService` (lifecycle), `MotionService` (moves + safe Z-ordering + sequences)
- **Dependency injection** (`app_factory.py`) — `create_services(use_mock=True/False)` wires everything; `create_app()` builds standalone GUI
- **Config** — 7-layer merge chain: defaults.json → local overrides → env vars (`PI_STAGE_CONFIG_PATH`)

### Camera & Vision Pipeline
- `device_drivers/thorlabs_camera_wrapper.py` — pylablib wrapper: snap, continuous grab, 16→8-bit normalization, exposure/gain/white-balance control
- `device_drivers/GPT_Merge.py` — Plate detection (Canny + morphology) and spot detection (adaptive threshold + contour filtering). Spot labeling with A1/A2/B1/B2 nomenclature
- `device_drivers/plate_finder.py` — HSV color segmentation for red frame + gray plate, outputs movement hints ("left", "right", "up", "down", "ok")
- `device_drivers/plate_auto_adjuster.py` — Closed-loop iterative centering (up to 10 iterations, 5mm step)

### Threading Model
- **Main thread**: Qt event loop, GUI rendering, QTimer camera polling (~100ms)
- **ThreadPoolExecutor** (4 named "PIControl" workers): All blocking hardware I/O (USB enumeration, reference moves, motor waits)
- **EventBus**: Services publish from executor threads; GUI handlers use `QMetaObject.invokeMethod` for thread safety
- **Cancellation**: Motion sequences use `threading.Event`

## Key Design Decisions

- **Frozen dataclasses** for all data models — thread safety via immutability
- **Safe Z-ordering** in MotionService: when lowering Z, move XY first; when raising Z, lift Z first
- **PI reference sequence**: Z must reference before X and Y (safety constraint)
- **DLL paths must be set before importing PI/Thorlabs libraries** — handled in `main.py` before any other imports
- `config/app_config.yaml` controls mock mode and DLL directories
- Artifacts (detection output images) go to `artifacts/plate_detection/` and `artifacts/we_detection/`
- `_archive/` contains previous implementations kept for reference — do not modify

## Testing

All tests use `MockAxisController` via dependency injection — no hardware required. Tests use `pytest-qt` for GUI testing. The conftest at `device_drivers/PI_Control_System/tests/conftest.py` adds `device_drivers/` to `sys.path`.


## Closeout and Commit Rules

**When the user requests to commit or closeout work, follow these steps:**

### 1. Clean Up Project Structure

- Delete or archive files no longer in use
- Move temporary/supporting files to appropriate folders
- Ensure project structure matches the File Organization section above
- Remove any debug code, commented-out blocks, or TODO placeholders that were resolved

### 2. Update Documentation

- Update `CLAUDE.md` with current state and major workflow changes
- Update any guidance documents affected by the changes
- **Critical:** All docs accessed during session init must be up-to-date
  - See **Session Initialization (REQUIRED)** section at top of this file

### 3. Prepare Commit

- **Primary branch:** `gd` — All development continues here (no merge to `main` planned)
- Stage relevant changes with `git add`
- Create commit with descriptive message following `<type>: <description>` format
- **Do NOT push** — wait for user's final review and approval
- Verify commit author is set correctly:
  ```bash
  git config user.name "GDSandStorm"
  git config user.email "qq1025938761@gmail.com"
  ```

### 4. Commit Message Format

```
<type>: <concise description>

<optional body with details>
```

Types: `feat`, `fix`, `refactor`, `docs`, `test`, `chore`

**Do NOT include:**
- AI co-author lines
- References to AI-assisted development
- "Generated by" or similar attributions

---