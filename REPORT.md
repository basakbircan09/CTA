# CTA — Camera, Thorlabs & Automation Module
## Technical Delivery Report

**Date:** 2026-02-16
**Repository:** `CTA/` (branch: `gd`)
**Context:** Module for the General Orchestrator for Electrochemistry Devices (GOED)
**Intended output:** Conference poster — automated electrochemistry workflow

---

## 1. Purpose and Scope

CTA is a standalone instrument-control module that bridges a **Thorlabs CS165CU scientific camera** and a **PI three-axis XYZ translation stage** (Physik Instrumente, model C-863/Mercury) into a single GUI application for **automated sample-array processing** in electrochemistry experiments.

The module provides:

- Motorised stage positioning with collision-safe Z-ordering
- Live camera preview, capture, and configurable exposure/gain/white balance
- Computer-vision-based plate detection and centering (closed-loop)
- Working-electrode (WE) spot inspection with bubble/hole defect classification
- A modular, event-driven architecture designed for integration into GOED

CTA is designed to become the **vision-and-positioning subsystem** within GOED, which orchestrates three device stacks (Gamry potentiostat, PI stages, Thorlabs camera) for unattended electrochemistry sequences.

---

## 2. System Architecture

### 2.1 High-Level Structure

```
main.py                          Thin entry point (DLL setup + launch)
    │
    ▼
gui/app_window.py                Orchestrator window — wires widgets to services
    │
    ├── gui/widgets/toolbar.py           Workflow buttons + status indicator
    ├── gui/widgets/camera_settings.py   Exposure, gain, white balance controls
    ├── gui/widgets/stage_control.py     Jog, go-to, position display
    ├── gui/widgets/image_viewer.py      OpenCV-to-Qt image display
    └── gui/widgets/log_panel.py         Timestamped log output
    │
    ▼
device_drivers/
    ├── PI_Control_System/               Three-axis stage subsystem
    │   ├── core/models.py               Immutable data models (Axis, Position)
    │   ├── services/connection_service   Hardware lifecycle (connect/init/shutdown)
    │   ├── services/motion_service       Motion orchestration (jog, goto, sequences)
    │   ├── services/event_bus            Thread-safe publish/subscribe
    │   ├── hardware/pi_controller        Real PI hardware via pipython
    │   ├── hardware/mock_controller      Deterministic mock for testing
    │   └── hardware/pi_manager           Multi-axis coordination
    │
    ├── thorlabs_camera_wrapper.py       Camera I/O via pylablib
    ├── GPT_Merge.py                     Plate + spot detection pipeline
    ├── plate_finder.py                  Plate-in-frame detection + hints
    └── plate_auto_adjuster.py           Closed-loop centering algorithm

config/
    ├── app_config.yaml                  Application-level configuration
    └── app_config_loader.py             YAML configuration loader
```

### 2.2 Design Patterns

| Pattern | Where applied | Rationale |
|---------|--------------|-----------|
| **Dependency injection** | `app_factory.create_services()` | Testability, mock/real hardware swap |
| **Event bus (pub/sub)** | `EventBus` with `EventType` enum | Decouples hardware threads from GUI |
| **Futures / thread pool** | `ThreadPoolExecutor` (4 workers) | Non-blocking hardware I/O |
| **State machine** | `ConnectionState` enum (6 states) | Prevents invalid operations |
| **Immutable models** | `frozen=True` dataclasses | Thread-safe state snapshots |
| **Strategy** | `AxisController` ABC | Swappable real vs mock hardware |
| **Signal/slot** | PySide6 signals between widgets | Loose coupling in GUI layer |
| **Configuration merge chain** | 7-layer config loader | Layered defaults + overrides |

### 2.3 Threading Model

```
Main Thread (Qt event loop)
    │
    ├── GUI rendering, user interaction
    ├── QTimer (100 ms) for live camera preview
    └── Signal/slot dispatch

ThreadPoolExecutor (4 workers)
    │
    ├── ConnectionService.connect()        blocking USB enumeration
    ├── ConnectionService.initialize()     blocking reference moves
    ├── MotionService.move_*()             blocking motor waits
    └── MotionService.execute_sequence()   waypoint loops

EventBus
    │
    └── Thread-safe publish from workers → subscribe in GUI handlers
```

---

## 3. Hardware Integration

### 3.1 PI XYZ Stage

**Hardware:** Three PI C-863 Mercury controllers, one per axis (X, Y, Z), connected via USB (COM3/4/5).

**Initialisation sequence per axis:**
1. `CST` — configure stage type (model 62309260)
2. `SVO` — enable servo loop
3. `FPL` — execute reference move (find negative limit)
4. `MVR -0.1` — back off limit switch
5. `VEL` — set default velocity (10 mm/s, max 20 mm/s)

**Reference order:** Z first (safety), then X, then Y.

**Travel ranges:**

| Axis | Min (mm) | Max (mm) | Park (mm) |
|------|----------|----------|-----------|
| X | 5.0 | 200.0 | 200.0 |
| Y | 0.0 | 200.0 | 200.0 |
| Z | 15.0 | 200.0 | 200.0 |

**Safety features:**
- All target positions clamped to configured travel range
- `move_to_position_safe_z()`: if lowering Z, moves XY first then Z down; if raising Z, lifts Z first then moves XY — prevents collision with sample
- Park sequence: Z lifts first, then XY move together

### 3.2 Thorlabs CS165CU Camera

**Interface:** `pylablib.devices.Thorlabs.ThorlabsTLCamera` via Thorlabs ThorCam SDK DLLs.

**Capabilities:**
- Frame acquisition via `snap()` (single frame) or continuous grab
- 16-bit colour/grayscale to 8-bit BGR conversion with per-channel normalisation
- Software white balance with presets (Default, Warm, Cool, Reduce NIR, Custom)
- Configurable exposure (1–5000 ms) and gain (0–48 dB)
- Live preview at ~10 fps via QTimer polling

---

## 4. Computer Vision Pipeline

### 4.1 Plate Detection (`GPT_Merge.py`)

Detects a rectangular sample plate and its circular working-electrode spots.

**Pipeline:**
1. **Plate localisation:** Grayscale → Gaussian blur → Canny edge detection (thresholds 45/40) → morphological dilation → largest contour → bounding rectangle
2. **Spot detection:** Adaptive Gaussian threshold (block 49) → morphological opening → contour filtering by area (300–15,000 px) and circularity (>0.4)
3. **Spot labelling:** Sort by Y (row grouping via median gap), then X within row → label as A1, A2, B1, B2, ...
4. **Defect classification:** Per spot, check intensity coefficient of variation (bubble: CV > 0.3) and topology hierarchy (hole: enclosed contour)

**Output:** Accepted/rejected spot lists, annotated visualisation images, plate bounding box.

### 4.2 Plate Positioning (`plate_finder.py`)

Determines if a grey plate is fully centred within a red sample holder frame.

**Method:**
- HSV colour segmentation for red frame detection (two hue ranges for red wraparound)
- Non-red + dark region intersection for plate detection
- Polygon approximation (4-sided, aspect ratio 0.5–2.0) for plate boundary
- Frame check with configurable margin (default 2%)
- Movement hint generation: `"left"`, `"right"`, `"up"`, `"down"`, `"ok"`, or compound directions

### 4.3 Auto-Adjustment (`plate_auto_adjuster.py`)

Closed-loop iterative centering of the plate under the camera.

```
for iteration in 1..max_iterations:
    frame = camera.capture()
    result = gray_plate_on_red(frame)
    if result.fully_in_frame:
        return SUCCESS
    hint → (dx, dy)   # e.g. "left" → dx = +step_mm
    stage.move_relative(X, dx)
    stage.move_relative(Y, dy)
    wait for completion
return INCOMPLETE
```

**Parameters:** step size (default 5 mm), max iterations (default 10).

---

## 5. GUI Design

**Framework:** PySide6 (Qt 6 for Python)
**Window:** 1400 x 850 px

```
┌─────────────────────────────────────────────────────────────────┐
│ [● STATUS]  [Connect] [Initialize] [Camera] [Capture]          │
│             [Plate Detect] [Auto Adjust] [WE Detect]           │
├───────────────────┬─────────────────────────────────────────────┤
│  Camera Settings  │                                             │
│  ┌─────────────┐  │          Image Viewer                       │
│  │ Exposure     │  │   (live preview / captured / processed)    │
│  │ Gain         │  │                                             │
│  │ White Balance│  │                                             │
│  └─────────────┘  │                                             │
│  Stage Control    │                                             │
│  ┌─────────────┐  │                                             │
│  │ Position XYZ │  │                                             │
│  │ Jog ± buttons│  │                                             │
│  │ Go-to target │  │                                             │
│  └─────────────┘  │                                             │
├───────────────────┴─────────────────────────────────────────────┤
│  Log Panel  [INFO] Stage: all controllers connected             │
│             [INFO] Exposure set to 100.0 ms                     │
└─────────────────────────────────────────────────────────────────┘
```

**Workflow (7 steps):**

| Step | Button | Action |
|------|--------|--------|
| 1 | Connect | USB connection to all three PI controllers |
| 2 | Initialize | Reference all axes (Z→X→Y), park at (200, 200, 200) |
| 3 | Camera | Toggle live preview (~10 fps) |
| 4 | Capture | Save frame as PNG with settings-encoded filename |
| 5 | Plate Detect | Run vision pipeline, show cropped plate + spot map |
| 6 | Auto Adjust | Closed-loop centering (capture → detect → move → repeat) |
| 7 | WE Detect | Bubble/hole defect analysis on detected spots |

---

## 6. Test Coverage

**123 automated tests** covering the PI_Control_System subsystem:

| Module | Tests | Coverage area |
|--------|-------|--------------|
| `test_models.py` | Axis enum, Position immutability, TravelRange clamping | Data integrity |
| `test_event_bus.py` | Subscribe/publish, token-based unsubscribe, exception isolation | Event system |
| `test_mock_controller.py` | State transitions, simulated motion, configurable failures | Hardware mock |
| `test_pi_controller.py` | GCSDevice wrapping, init sequence, position queries | Real hardware (mocked SDK) |
| `test_pi_manager.py` | Multi-axis connect, Z→X→Y init order, park sequence | Coordination |
| `test_connection_service.py` | State machine transitions, event publishing, async ops | Service layer |
| `test_motion_service.py` | Single/multi-axis moves, safe Z ordering, sequence cancellation | Motion control |
| `test_app_factory.py` | Dependency injection, service wiring, shared resources | Integration |
| `test_widgets.py` | Widget rendering, signal emission, state updates | GUI components |
| `test_config.py` | JSON load, merge chain, schema validation, hardcoded fallback | Configuration |
| `test_immutability.py` | Frozen dataclass enforcement | Thread safety |

All tests use `MockAxisController` for deterministic, hardware-independent execution.

---

## 7. Configuration System

### Application config (`config/app_config.yaml`):
```yaml
app:
  use_mock_stage: true
  examples_dir: "./examples"
thorlabs:
  dll_dir: "C:\\Program Files\\Thorlabs\\ThorImageCAM\\Bin"
paths:
  pi_dll_dir: "./lib/pi_dlls"
```

### PI stage config (7-layer merge chain):
1. Package defaults (`defaults.json`)
2. Package-level overrides (`config/local.overrides.json`)
3. Root-level overrides (`local.overrides.json`)
4. Environment variable (`PI_STAGE_CONFIG_PATH`)
5. Explicit path parameter
6. Deep merge with validation
7. `ConfigBundle` output (frozen, validated)

---

## 8. Codebase Metrics

| Metric | Value |
|--------|-------|
| Entry point (`main.py`) | 28 lines |
| Orchestrator (`gui/app_window.py`) | 346 lines |
| Widget modules (5 files) | 435 lines total |
| PI_Control_System subsystem | ~2,500 lines (production + tests) |
| Vision pipeline (3 files) | ~450 lines |
| Camera wrapper | ~200 lines |
| Automated tests | 123 (all passing) |
| DLLs relocated to `lib/pi_dlls/` | ~31 MB |
| Legacy code archived | `_archive/` (3 directories + 11 files) |

---

## 9. Integration Path to GOED

CTA is designed as a **self-contained device module** that maps directly into GOED's architecture:

```
GOED Orchestrator Core
    │
    ├── Gamry wrapper       (potentiostat control)
    ├── CTA module          (camera + stage + vision)     ◄── this deliverable
    └── future devices...
```

**Integration points:**

| GOED concept | CTA implementation |
|-------------|-------------------|
| Device wrapper process | `main.py` can be launched as subprocess; services expose programmatic API |
| JSON IPC commands | Sequence YAML definitions already in `examples/` (same schema as GOED sequences) |
| State machine | `ConnectionState` enum (DISCONNECTED → CONNECTING → CONNECTED → INITIALIZING → READY → ERROR) aligns with GOED's device state model |
| Health/status | `EventBus` publishes 15+ event types; `connection_service.is_ready()` for health checks |
| Mock/dry-run | `use_mock=True` enables full offline testing without hardware |
| Experiment manifest | Captures saved to `artifacts/` with settings-encoded filenames; plate/spot results returned as structured dicts |

**What GOED adds on top:**
- Cross-device sequencing (e.g., "move stage → capture → run CV measurement")
- Unified dashboard aggregating CTA + Gamry telemetry
- Run manifests tying all device outputs to a single experiment ID
- Retry policies, interlocks, and operator acknowledgements

---

## 10. Technology Stack

| Component | Technology | Version |
|-----------|-----------|---------|
| Language | Python | 3.13 |
| GUI framework | PySide6 (Qt 6) | latest |
| Stage SDK | pipython (PI GCS2) | latest |
| Camera SDK | pylablib + Thorlabs ThorCam | latest |
| Computer vision | OpenCV (`opencv-python`) | latest |
| Image I/O | tifffile, OpenCV | latest |
| Numerical | NumPy | latest |
| Configuration | PyYAML | latest |
| Testing | pytest, pytest-qt | latest |
| OS | Windows 10/11 (x64) | required for vendor DLLs |

---

## 11. Repository Structure (Final)

```
CTA/
    main.py                              Entry point (28 lines)
    requirements.txt                     Dependencies (9 packages)
    .gitignore                           Excludes archive, artifacts, build dirs

    config/
        app_config.yaml                  Application configuration
        app_config_loader.py             YAML config loader

    gui/
        app_window.py                    Main window orchestrator (346 lines)
        widgets/
            toolbar.py                   Workflow toolbar + status
            camera_settings.py           Exposure, gain, white balance
            stage_control.py             Position, jog, go-to
            image_viewer.py              OpenCV ↔ Qt image display
            log_panel.py                 Timestamped log output

    device_drivers/
        PI_Control_System/               Three-axis stage control (unchanged)
            core/                        Models, errors, interfaces
            services/                    ConnectionService, MotionService, EventBus
            hardware/                    PIAxisController, MockAxisController, Manager
            config/                      JSON config loader + schema
            tests/                       123 automated tests
        thorlabs_camera_wrapper.py       Camera I/O
        GPT_Merge.py                     Plate + spot detection
        plate_finder.py                  Plate-in-frame analysis
        plate_auto_adjuster.py           Closed-loop centering

    lib/pi_dlls/                         PI controller DLLs (~31 MB)
    examples/                            YAML sequence definitions
    _archive/                            Legacy code (preserved for git history)
```

---

## 12. Current Status and Limitations

### Delivered
- Fully modular GUI with signal/slot widget architecture
- Complete PI three-axis stage control with safety features
- Thorlabs camera integration with live preview
- Computer vision plate detection and defect classification
- Closed-loop auto-adjustment workflow
- 123 passing automated tests
- Clean project structure with archived legacy code

### Known Limitations
- Camera and vision pipeline tests rely on real hardware (no camera mock yet)
- `auto_adjust_plate()` runs synchronously on the main thread (blocks GUI during iterations)
- White balance is software-only (no hardware WB support in ThorlabsTLCamera)
- Vision parameters (Canny thresholds, area filters, circularity) are constants — not yet exposed in config
- Single-PC Windows-only due to vendor DLL dependencies

### Recommended Next Steps
1. Add a `MockCamera` for offline vision pipeline testing
2. Move `auto_adjust_plate()` to background thread with progress signals
3. Expose vision parameters in `app_config.yaml`
4. Implement GOED wrapper interface (JSON IPC command handler)
5. Add structured experiment logging with run IDs for GOED manifest integration
