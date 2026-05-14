# CTA – Camera, Thorlabs & Automation

A PySide6 desktop application for automated electrochemistry sample-array processing. It integrates a **Thorlabs CS165CU** scientific camera, a **PI three-axis XYZ translation stage** (3× C-863 Mercury controllers), and a full **OpenCV-based vision pipeline** for plate finding, spot detection, defect inspection, and SFC alignment.

CTA is designed as a subsystem for the **GOED (General Orchestrator for Electrochemistry Devices)** platform.

---

## Table of Contents

1. [Overview](#overview)
2. [The Normal Workflow](#the-normal-workflow)
3. [Architecture](#architecture)
4. [Project Structure](#project-structure)
5. [Hardware Requirements](#hardware-requirements)
6. [Software Requirements & Installation](#software-requirements--installation)
7. [How to Run](#how-to-run)
8. [Application UI – Button-by-Button](#application-ui--button-by-button)
9. [Camera Settings Panel](#camera-settings-panel)
10. [Stage Control Panel](#stage-control-panel)
11. [Vision & Analysis Pipeline](#vision--analysis-pipeline)
12. [Spot Analysis Module](#spot-analysis-module)
13. [Spot Alignment (Pixel → Stage)](#spot-alignment-pixel--stage)
14. [Full File Reference](#full-file-reference)
15. [Output Artifacts](#output-artifacts)
16. [Configuration](#configuration)
17. [Testing](#testing)
18. [Key Design Decisions](#key-design-decisions)

---

## Overview

CTA brings three physical subsystems together in one GUI:

| Subsystem | Hardware | Purpose |
|---|---|---|
| **PI XYZ Stage** | 3× C-863 Mercury controllers | Sub-millimetre positioning of the plate under the camera or SFC probe |
| **Thorlabs Camera** | CS165CU (pylablib) | Live view and image capture for vision analysis |
| **Vision Pipeline** | OpenCV, NumPy | Plate detection, working-electrode spot detection, defect inspection, SFC alignment |

---

## The Normal Workflow

This is the step-by-step sequence an operator follows every session:

```
1. Connect     →  USB-enumerate all three PI axes (X, Y, Z)
2. Initialize  →  Run reference moves in safe order (Z first, then X, Y)
3. Start Live  →  Begin camera preview at ~100 ms poll rate
4. Capture     →  Snap a full-resolution image and save it to disk
5. Plate Detect→  Locate the red-framed plate in the captured image
6. Auto Adjust →  Closed-loop centering: move stage until plate is centred (≤10 iterations, 5 mm steps)
7. WE Detect   →  Detect all working-electrode spots; inspect each for defects; export Excel report
```

After **WE Detect** the operator can also use the **Stage Control Panel** to manually jog axes and the camera settings panel to tune exposure, gain, and white balance.

---

## Architecture

```
main.py
│
├── gui/app_window.py          ← Main orchestrator (SimpleStageApp)
│   └── gui/widgets/
│       ├── toolbar.py         ← WorkflowToolbar (Connect → WE Detect buttons)
│       ├── camera_settings.py ← Exposure / gain / white-balance controls
│       ├── stage_control.py   ← Per-axis jog controls + absolute move
│       ├── image_viewer.py    ← Zoomable image display (QGraphicsView)
│       └── log_panel.py       ← Scrollable timestamped log
│
├── device_drivers/
│   ├── thorlabs_camera_wrapper.py   ← pylablib snap/live/settings
│   ├── GPT_Merge_v3.py              ← Plate + spot detection (active version)
│   ├── plate_finder.py              ← HSV colour segmentation → movement hints
│   ├── plate_auto_adjuster.py       ← Closed-loop iterative centering
│   ├── spot_alignment.py            ← Pixel-to-stage coordinate mapping
│   ├── image_utils.py               ← load / save / colour conversion helpers
│   └── spot_analysis/               ← Modular spot inspection pipeline
│       ├── pipeline.py              ← Public entry-point: run_spot_analysis()
│       ├── detection.py             ← Preprocessing + contour-based spot finding
│       ├── inspection.py            ← Per-spot defect scoring (MAD / quantile)
│       ├── visualization.py         ← Accept/reject overlay images
│       ├── excel_export.py          ← spot_results.xlsx export (openpyxl)
│       └── config.py                ← All tunable detection constants
│
└── device_drivers/PI_Control_System/   ← Self-contained PI stage subsystem
    ├── app_factory.py               ← create_services(use_mock) wires everything
    ├── core/models.py               ← Frozen dataclasses: Axis, Position, states
    ├── core/hardware/interfaces.py  ← AxisController ABC
    ├── hardware/pi_manager.py       ← Coordinates 3 axes, enforces Z→X→Y ref order
    ├── hardware/pi_controller.py    ← Real pipython implementation
    ├── hardware/mock_controller.py  ← Deterministic mock for tests
    ├── services/event_bus.py        ← Thread-safe pub/sub
    ├── services/connection_service.py
    ├── services/motion_service.py   ← Moves + safe Z-ordering + sequences
    └── config/                      ← 7-layer merge (defaults.json → env vars)
```

### Threading model

| Thread | What runs there |
|---|---|
| Main (Qt event loop) | All GUI rendering, QTimer camera poll (~100 ms) |
| `ThreadPoolExecutor` (4 × "PIControl") | All blocking hardware I/O: USB enumeration, reference moves, motor waits |
| `QThread` workers | `SpotAnalysisWorker` and `WeGptWorker` — keep WE Detect off the UI thread |
| `EventBus` | Services publish from executor threads; GUI uses `QMetaObject.invokeMethod` to hop back to the main thread |

---

## Project Structure

```
CTA/
├── main.py                       ← Entry point (sets DLL paths, launches app)
├── requirements.txt
├── config/
│   └── app_config_loader.py      ← Loads app_config.yaml (mock mode, DLL dirs)
├── gui/
│   ├── app_window.py
│   └── widgets/
├── device_drivers/
│   ├── PI_Control_System/
│   │   └── tests/                ← 123 pytest tests (no hardware needed)
│   └── spot_analysis/
├── lib/
│   └── pi_dlls/                  ← PI GCS2 DLL files (Windows)
├── artifacts/
│   ├── plate_detection/          ← Plate detect output images
│   └── we_detection/             ← WE Detect debug images + spot_results.xlsx
├── doc/                          ← Supporting documentation
├── examples/                     ← Example images / scripts
├── _archive/                     ← Previous implementations (read-only reference)
└── REPORT.md                     ← Lab report / experiment notes
```

---

## Hardware Requirements

| Item | Details |
|---|---|
| **PI C-863 Mercury** | 3 units, one per axis (X, Y, Z). Connected via USB-serial. |
| **Thorlabs CS165CU** | USB3 scientific camera. Requires Thorlabs ThorCam SDK DLLs. |
| **Windows 10/11** | DLL loading (`os.add_dll_directory`) is Windows-only. |

> **No hardware?** Run with `use_mock=True` (see [How to Run](#how-to-run)). The mock stage behaves identically for all tests and most GUI operations.

---

## Software Requirements & Installation

```bash
pip install -r requirements.txt
```

`requirements.txt`:
```
PySide6
pipython
numpy
pylablib
opencv-python
scikit-image
PyYAML
tifffile
openpyxl
pytest
pytest-qt
```

**Additional DLLs (Windows only)**

- PI GCS2 DLLs → place in `lib/pi_dlls/` (or set `PI_STAGE_CONFIG_PATH`)
- Thorlabs ThorCam SDK → typically `C:\Program Files\Thorlabs\ThorImageCAM\Bin`; configure path in `config/app_config.yaml`

---

## How to Run

```bash
# With real hardware
python main.py

# With mock stage (no hardware needed)
# Edit config/app_config.yaml: use_mock: true
# OR directly in code: SimpleStageApp(use_mock=True)
python main.py
```

`main.py` sets up PI DLL paths **before** any imports, then launches `SimpleStageApp`.

---

## Application UI – Button-by-Button

The toolbar runs left-to-right in the order you use them:

### 1. Connect
- Scans USB ports for PI C-863 controllers.
- Establishes serial connections for all three axes (X, Y, Z).
- Runs asynchronously in the `PIControl` thread pool.
- On success: **Initialize** becomes enabled.

### 2. Initialize
- Runs reference moves in the mandatory safe order: **Z first, then X, then Y**.
- Each axis moves to its hardware limit switch and sets that as the origin.
- On completion: motion commands and **Start Live** become available.

### 3. Start Live / Stop Live
- Toggles the camera preview using a 100 ms `QTimer`.
- Each tick calls `ThorlabsCamera.snap()` and updates the `ImageViewer`.
- Stop live before capturing to get a stable full-resolution frame.

### 4. Capture
- Snaps a full-resolution image from the camera.
- Saves it to `artifacts/plate_detection/captured_<timestamp>.png`.
- Displays it in the `ImageViewer`.
- Enables **Plate Detect**.

### 5. Plate Detect
- Runs `GPT_Merge_v3.analyze_plate_and_spots()` on the captured image.
- Uses Canny edge detection + morphology to find the plate boundary.
- Uses adaptive threshold + contour filtering to find electrode spots.
- Labels spots with A1/A2/B1/B2 etc. nomenclature.
- Overlays results on the image and logs a summary.
- Enables **Auto Adjust**.

### 6. Auto Adjust
- Calls `plate_auto_adjuster.auto_adjust_plate()`.
- Runs `plate_finder.py` (HSV colour segmentation) to get a movement hint: `"left"`, `"right"`, `"up"`, `"down"`, or `"ok"`.
- Moves the stage by 5 mm in the indicated direction.
- Repeats up to 10 iterations until hint is `"ok"` or iteration limit reached.
- Enables **WE Detect** once complete.

### 7. WE Detect
- Runs the full `spot_analysis` pipeline in a background `QThread`.
- Detects all working-electrode spots and inspects each for defects.
- Saves 10 debug images to `artifacts/we_detection/`.
- Exports `spot_results.xlsx` with per-spot metrics.
- Displays the accept/reject colour overlay in the `ImageViewer`.

---

## Camera Settings Panel

| Control | Effect |
|---|---|
| **Exposure** | Sets integration time (µs). Auto-exposure off. |
| **Gain** | Analogue gain multiplier. |
| **White Balance** | R / G / B channel multipliers for colour correction. |
| **Apply** | Pushes current settings to `ThorlabsCamera`. |

Settings take effect on the next `snap()` call.

---

## Stage Control Panel

| Control | Effect |
|---|---|
| **X / Y / Z jog buttons** | Move axis by the configured step size. |
| **Step size** | Editable spin-box (mm). |
| **Go to position** | Absolute move to typed X, Y, Z coordinates. |
| **Park** | Move to park position (default 200, 200, 200 mm). |

All moves go through `MotionService` which enforces safe Z-ordering (see [Key Design Decisions](#key-design-decisions)).

---

## Vision & Analysis Pipeline

### Plate detection (`GPT_Merge_v3.py`)
1. Convert to grayscale → Canny edges → morphological close/dilate → find largest closed contour → plate bounding box.
2. Adaptive threshold on the plate crop → filter contours by area, circularity, solidity → electrode spots.
3. Sort spots into a grid, assign A1/A2/… labels.

### Plate finder (`plate_finder.py`)
- HSV colour segmentation: isolates the red frame (hue wraps 0/180°) and the grey plate interior.
- Computes centroid offset from image centre → returns one of: `"left"`, `"right"`, `"up"`, `"down"`, `"ok"`.

---

## Spot Analysis Module

`device_drivers/spot_analysis/` is a self-contained pipeline callable independently of the GUI:

```python
from device_drivers.spot_analysis.pipeline import run_spot_analysis

result = run_spot_analysis(
    image_path="path/to/plate.png",
    output_dir="artifacts/we_detection",
    export_excel=True,
)
```

### Returned dict keys

| Key | Type | Description |
|---|---|---|
| `all_spots` | `list[dict]` | All accepted candidate spots (with labels) |
| `accepted_spots` | `list[dict]` | Spots with no detected defects |
| `rejected_spots` | `list[dict]` | Spots flagged as defective |
| `rejected_candidates` | `list[dict]` | Contours filtered out during detection |
| `overlay_image` | `np.ndarray` | BGR accept/reject colour overlay |
| `accepted_labels` | `list[str]` | e.g. `["A1", "A2", "B3"]` |
| `rejected_labels` | `list[str]` | e.g. `["B1"]` |
| `missing_spots` | `list[str]` | Expected grid labels that are absent |
| `per_spot_metrics` | `dict` | `{label: metrics_dict}` for every accepted spot |
| `excel_path` | `str \| None` | Path to `spot_results.xlsx`, or `None` |
| `error` | `str \| None` | Non-fatal error string, or `None` |

### Detection pipeline steps

| Step | File | What happens |
|---|---|---|
| Grayscale + background normalisation | `detection.py` | Large-kernel Gaussian blur estimates illumination; divide-normalise removes it |
| CLAHE | `detection.py` | Local contrast enhancement |
| Adaptive threshold | `detection.py` | Binarise with adaptive block size |
| Morphological open/close | `detection.py` | Remove noise, fill gaps |
| Contour filter | `detection.py` | Area, circularity ≥ 0.45, solidity ≥ 0.65, diameter ≥ 1.5 mm |
| Grid sort + labelling | `detection.py` | Spots sorted row-major → A1, A2, … |
| Defect inspection | `inspection.py` | MAD outlier test + dark/bright quantile test per spot |
| Visualisation | `visualization.py` | Green (accept) / red (reject) overlay |
| Excel export | `excel_export.py` | `spot_results.xlsx` with per-spot metrics |

### Tunable constants (`spot_analysis/config.py`)

```python
DEFAULT_MIN_SPOT_AREA       = 450      # px²
DEFAULT_MAX_SPOT_AREA       = 15000    # px²
DEFAULT_MIN_CIRCULARITY     = 0.45
DEFAULT_MIN_SOLIDITY        = 0.65
DEFAULT_PLATE_WIDTH_MM      = 50.0     # physical plate width (mm)
DEFAULT_MIN_SPOT_DIAMETER_MM = 1.5    # minimum spot diameter (mm)
DEFAULT_MAD_K               = 4.5     # MAD outlier multiplier
DEFAULT_MAX_OUTLIER_FRAC    = 0.16    # max fraction of outlier pixels
DEFAULT_DEFECT_AREA_FRAC    = 0.03    # min defect area as fraction of spot
```

---

## Spot Alignment (Pixel → Stage)

`device_drivers/spot_alignment.py` converts pixel coordinates (selected in the GUI via `ManualSpotDialog`) into absolute stage XY targets and produces Z-safe motion sequences.

**Lab calibration constants** (edit here when the setup is re-calibrated):

| Constant | Value | Meaning |
|---|---|---|
| `PIXEL_SCALE_MM` | 0.095 mm/px | Physical scale of one pixel |
| `SFC_X`, `SFC_Y`, `SFC_Z` | 153.0, 83.0, 156.0 mm | Absolute stage position of the SFC opening |
| `APPROACH_Z` | 161.0 mm | Z stop height before final contact (SFC_Z + 5 mm) |
| Reference stage at capture | X=212.5, Y=206.1 mm | Stage position when the image was taken |

**Z-safety rules enforced by `SpotAligner`:**
1. Never move Z downward before XY alignment is complete.
2. Always raise Z before moving between spots.
3. Always stop at `APPROACH_Z` — never descend to `SFC_Z` here.
4. Never go directly spot-to-spot without lifting Z.

---

## Full File Reference

### `main.py`
Entry point. Sets up `lib/pi_dlls/` on `PATH` and `os.add_dll_directory` before any PI/Thorlabs imports. Defines two background workers:
- `SpotAnalysisWorker(QThread)` — runs `run_spot_analysis()` off the UI thread.
- `WeGptWorker(QThread)` — runs `GPT_Merge_v3.analyze_plate_and_spots()` off the UI thread.

Then launches `SimpleStageApp(use_mock=False)`.

### `gui/app_window.py`
Main window (`SimpleStageApp`, ~460 lines). Wires all widgets, implements all workflow handlers (connect, initialize, capture, detect, adjust, WE detect). Uses `QMetaObject.invokeMethod` for thread-safe GUI updates from the `EventBus`.

### `gui/widgets/toolbar.py`
`WorkflowToolbar` — horizontal row of workflow buttons. Emits signals consumed by `app_window.py`.

### `gui/widgets/camera_settings.py`
Exposure, gain, white-balance controls. Calls `ThorlabsCamera` setters on Apply.

### `gui/widgets/stage_control.py`
Jog buttons, step size, absolute-move form, park button. Calls `MotionService`.

### `gui/widgets/image_viewer.py`
`ImageViewer` wraps `QGraphicsView` for zoomable, pannable image display.

### `gui/widgets/log_panel.py`
`LogPanel` — scrollable `QTextEdit` with timestamped log lines.

### `config/app_config_loader.py`
`load_app_config()` — reads `app_config.yaml` (mock mode flag, DLL directories).

### `device_drivers/thorlabs_camera_wrapper.py`
`ThorlabsCamera` — thin pylablib wrapper. Methods: `snap()`, `start_live()`, `stop_live()`, `set_exposure()`, `set_gain()`, `set_white_balance()`. Converts 16-bit sensor output to 8-bit for display.

### `device_drivers/GPT_Merge_v3.py`
Active plate + spot detection entry point. `analyze_plate_and_spots(image)` → dict with plate bbox, spot list, labelled overlay. (`GPT_Merge.py` and `GPT_Merge_v2.py` are older iterations kept for reference.)

### `device_drivers/plate_finder.py`
HSV colour segmentation for the red frame and grey plate. Returns a movement hint string for the auto-adjuster.

### `device_drivers/plate_auto_adjuster.py`
`auto_adjust_plate(camera, motion_service)` — closed-loop centering loop (≤10 iterations, 5 mm step per iteration).

### `device_drivers/spot_alignment.py`
`SpotAligner` + `AlignmentResult` — pixel-to-stage coordinate conversion and Z-safe motion sequence generation.

### `device_drivers/image_utils.py`
Utility functions: `load_image()`, `save_image()`, `bgr_to_rgb()`.

### `device_drivers/spot_analysis/`
See [Spot Analysis Module](#spot-analysis-module) above.

### `device_drivers/PI_Control_System/`
Self-contained PI stage subsystem. Entry point: `app_factory.create_services(use_mock)`.

| File | Role |
|---|---|
| `core/models.py` | Frozen dataclasses: `Axis`, `Position`, `ConnectionState`, `InitializationState` |
| `core/hardware/interfaces.py` | `AxisController` ABC |
| `hardware/pi_manager.py` | Coordinates 3 axes; enforces Z→X→Y reference order |
| `hardware/pi_controller.py` | Real `pipython` implementation |
| `hardware/mock_controller.py` | Deterministic mock for testing |
| `services/event_bus.py` | Thread-safe pub/sub |
| `services/connection_service.py` | USB connection lifecycle |
| `services/motion_service.py` | Moves, safe Z-ordering, motion sequences |
| `config/` | 7-layer merge chain: `defaults.json` → local overrides → env var `PI_STAGE_CONFIG_PATH` |

PI stage CLI:
```bash
python -m device_drivers.PI_Control_System.config show
python -m device_drivers.PI_Control_System.config set --park-position X=200.0 Y=200.0 Z=200.0
```

---

## Output Artifacts

| Path | Contents |
|---|---|
| `artifacts/plate_detection/` | Captured images, plate detection overlays |
| `artifacts/we_detection/` | 10 debug images from `run_spot_analysis()` + `spot_results.xlsx` |

Debug image sequence written by `run_spot_analysis()`:

```
01_original.png
02_gray_raw.png
03_bg.png
04_gray_norm.png
05_blur.png
06_thresh_bw.png
07_opened.png
08_closed.png
09_rejected_candidates_overlay.png   ← yellow: contours filtered out
10_accept_reject_overlay.png         ← green: ok, red: defective
```

`spot_results.xlsx` sheets:
- **All_Spots** — every detected spot with metrics
- **Rejected_Spots** — defective spots only
- **Summary** — accepted/rejected counts, missing spots

---

## Configuration

### `config/app_config.yaml`
```yaml
use_mock: false          # true = no hardware required

thorlabs:
  dll_dir: "C:\\Program Files\\Thorlabs\\ThorImageCAM\\Bin"

pi_stage:
  config_path: ""        # override PI config directory (or set PI_STAGE_CONFIG_PATH env var)
```

### PI stage config (7-layer merge)
1. Built-in defaults (`defaults.json`)
2. User local overrides
3. Environment variable `PI_STAGE_CONFIG_PATH`

### Spot analysis constants
Edit `device_drivers/spot_analysis/config.py` to tune detection sensitivity without touching pipeline code.

---

## Testing

All 123 tests run without any hardware (uses `MockAxisController` via dependency injection):

```bash
# Run all tests
pytest device_drivers/PI_Control_System/tests/ -v

# Single module
pytest device_drivers/PI_Control_System/tests/test_motion_service.py -v

# With coverage
pytest --cov=device_drivers device_drivers/PI_Control_System/tests/
```

Tests use `pytest-qt` for GUI testing. `conftest.py` at `device_drivers/PI_Control_System/tests/conftest.py` adds `device_drivers/` to `sys.path`.

---

## Key Design Decisions

| Decision | Reason |
|---|---|
| **Frozen dataclasses** for all data models | Thread safety via immutability — no locks needed for read-only state |
| **Safe Z-ordering** in `MotionService` | When lowering Z: move XY first. When raising Z: lift Z first. Prevents collisions. |
| **PI reference sequence: Z before X, Y** | Physical safety constraint of this stage configuration |
| **DLL paths set before any imports** | `pipython` and pylablib load DLLs at import time; path must exist first |
| **`ThreadPoolExecutor` for hardware I/O** | Keeps USB/serial blocking calls off the Qt main thread |
| **`QThread` workers for vision** | `run_spot_analysis()` can take seconds; must not freeze the GUI |
| **`EventBus` + `invokeMethod`** | Services on worker threads publish events; GUI marshals back to main thread safely |
| **`_archive/`** | Old implementations kept for reference — do not modify |
