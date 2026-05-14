# CTA – Camera, Thorlabs & Automation

A PySide6 desktop application for automated electrochemistry sample-array processing. Integrates a **Thorlabs CS165CU** scientific camera, a **PI three-axis XYZ translation stage** (3× C-863 Mercury controllers), a **force sensor**, and a full **OpenCV vision pipeline** for plate detection, working-electrode spot inspection, and SFC probe alignment.

---

## Table of Contents

1. [Overview](#overview)
2. [The 7-Step Workflow](#the-7-step-workflow)
3. [Application UI](#application-ui)
4. [Button-by-Button Reference](#button-by-button-reference)
5. [Left Panel Reference](#left-panel-reference)
6. [Bottom Bar](#bottom-bar)
7. [Architecture & File Layout](#architecture--file-layout)
8. [Hardware Requirements](#hardware-requirements)
9. [Installation](#installation)
10. [How to Run](#how-to-run)
11. [Vision Pipeline Details](#vision-pipeline-details)
12. [Spot Analysis Module](#spot-analysis-module)
13. [Spot Alignment (Pixel → Stage)](#spot-alignment-pixel--stage)
14. [Output Artifacts](#output-artifacts)
15. [Configuration](#configuration)
16. [Testing](#testing)
17. [Key Design Decisions](#key-design-decisions)
18. [Dead / Unused Code](#dead--unused-code)

---

## Overview

| Subsystem | Hardware | Role |
|---|---|---|
| **PI XYZ Stage** | 3× C-863 Mercury (USB-serial) | Sub-millimetre positioning |
| **Thorlabs Camera** | CS165CU (pylablib) | Live view and image capture |
| **Force Sensor** | Serial bridge process | Contact detection during Z approach |
| **Vision Pipeline** | OpenCV / NumPy | Plate finding, spot detection, defect inspection |

---

## The 7-Step Workflow

The UI shows a **step progress bar** (colour-coded pills) that tracks where you are:

```
1. Connect  →  2. Camera  →  3. Capture  →  4. Detect Plate  →  5. Detect Spots  →  6. Move  →  7. Contact
```

Each toolbar button advances the relevant step indicator.

---

## Application UI

```
┌─────────────────────────────────────────────────────────────────────────────┐
│ [DISCONNECTED]  [Connect && Initialize]  [Start Camera]  [Capture Image]   │
│                 [Detect Plate]  [Detect Spots]  [Manual Select]             │
│                 [Move to Spot]  [Move Next]  [Make Contact]                 │
├─────────────────────────────────────────────────────────────────────────────┤
│ 1.Connect  2.Camera  3.Capture  4.Detect Plate  5.Detect Spots  6.Move  7.Contact │
├──────────────────────┬──────────────────────────────────────────────────────┤
│ Camera Settings      │                                                      │
│  Exposure (ms)  [Set]│                                                      │
│  Gain (dB)      [Set]│          Image Display Area                         │
│  Advanced ▼          │                                                      │
│    WB preset combo   │                                                      │
│    R / G / B spins   │                                                      │
│    [Apply WB]        │                                                      │
├──────────────────────┤                                                      │
│ Stage Control        │                                                      │
│  Position readout    │                                                      │
│  Step (mm)  [Refresh]│                                                      │
│  X: [-] [+]          │                                                      │
│  Y: [-] [+]          │                                                      │
│  Z: [-] [+]          │                                                      │
│  Go to X/Y/Z  [Go]   │                                                      │
├──────────────────────┤                                                      │
│ Spot Navigation      │                                                      │
│  Spot: [combo]  [Go] │                                                      │
│  [Next Spot]         │                                                      │
│  Next: S1 (1/4)      │                                                      │
│  [Contact]           │                                                      │
├──────────────────────┤                                                      │
│ SFC Calibration ▼    │                                                      │
│ Alignment Options ▼  │                                                      │
├──────────────────────┴──────────────────────────────────────────────────────┤
│ [Force Sensor]  [Stage Position]  [Log ─────────────────────────────────── │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## Button-by-Button Reference

### Toolbar

#### Connect && Initialize
- Runs connect + reference moves in one click.
- Internally calls `on_connect_clicked()` (USB-enumerates all 3 PI axes) then `on_initialize_clicked()` (reference Z → X → Y, then parks at X=200 Y=200 Z=200).
- Sets step indicator to step 1.
- Status label cycles: CONNECTING → INITIALIZING → PARKING → **READY** (green).

#### Start Camera / Stop Camera
- Toggles Thorlabs live view at ~100 ms poll rate.
- Sets step indicator to step 2.
- Button text flips between "Start Camera" and "Stop Camera".

#### Capture Image
- Sets step indicator to step 3.
- If camera is connected: snaps a full-resolution frame, saves to `artifacts/captures/Photo_<exp>_<gain>_<r>_<g>_<b>.png`.
- If camera is not available: falls back to a **file picker dialog** so you can load an existing image.
- Stores path as `last_image_path`.

#### Detect Plate
- Sets step indicator to step 4.
- Uses `last_image_path` (or prompts for a file if none).
- Runs `GPT_Merge.analyze_plate_and_spots()` → extracts plate bounding box and crops the plate image.
- Saves cropped plate to `artifacts/plate_detection/plate.png`.
- Displays the crop in the image area.
- Stores path as `last_plate_path`.

#### Detect Spots
- Sets step indicator to step 5.
- Uses `last_plate_path` (or prompts for a file).
- Runs `run_spot_analysis()` in a **background `QThread`** (`SpotAnalysisWorker`) so the UI stays responsive.
- Button label changes to "Detect Spots (running...)" while processing.
- On completion: displays the accept/reject overlay, logs accepted/rejected/missing spot counts, saves `spot_results.xlsx`.

#### Manual Select
- Opens `ManualSpotDialog` — an interactive image viewer where you click to mark:
  - One **Reference point** (click "Set Reference" then click on image)
  - One or more **Spot positions** (S1, S2, … — click directly on spots)
- Saves an annotated image and an Excel file to `artifacts/manual_spots/`.
- Populates the **Spot Navigation** combo box with S1, S2, …
- Required before "Move to Spot" or "Move Next" will work.

#### Move to Spot
- Sets step indicator to step 6.
- Reads the spot selected in the Spot Navigation combo box.
- Computes the pixel→stage offset via `SpotAligner.compute_alignment()`.
- Shows a **confirmation dialog** with ΔX, ΔY, target X/Y, approach Z, and move distance.
- If move distance exceeds the **Safety limit** (default 10 mm), shows an extra warning.
- Executes the Z-safe motion sequence in a background `SpotAlignmentWorker`.
- Respects "Dry Run" and "Flip X/Y" settings from Alignment Options.

#### Move Next
- Same as "Move to Spot" but always uses the **next unvisited spot** in sequence (S1 → S2 → S3 …).
- Each press advances one spot so you can supervise every step.
- Shows a confirmation dialog with remaining spots count.
- When all spots are visited, offers to reset back to S1.

#### Make Contact
- Sets step indicator to step 7.
- If a `ContactWorker` is already running, **aborts** it (button becomes "Stop Contact").
- Otherwise, starts a `ContactWorker` that:
  1. Moves Z to approach height (161 mm by default).
  2. Steps Z down 1 mm at a time.
  3. Reads force from `ForceSensorDisplay`.
  4. Stops when force > 2 N (contact detected) OR Z reaches 110 mm (limit reached).
- Reports contact result in a message box.

---

## Left Panel Reference

### Camera Settings
| Control | Range | Action |
|---|---|---|
| Exposure (ms) | 1–5000 ms | [Set] calls `camera.set_exposure()` |
| Gain (dB) | 0–48 dB | [Set] calls `camera.set_gain()` |
| **Advanced ▼** (collapsible) | | |
| White Balance preset | Default / Warm / Cool / Reduce NIR / Custom | Auto-applies when changed |
| R / G / B spinners | 0.1–4.0 | [Apply White Balance] calls `camera.set_white_balance()` |

### Stage Control
| Control | Description |
|---|---|
| Position readout | Shows last-known X / Y / Z (mm) |
| Step (mm) | Jog step size (0.1–50 mm) |
| [Refresh] | Reads current position from stage |
| X/Y/Z [-] [+] | Jogs axis by ± step size |
| Go to X / Y / Z | Absolute move with Z-safe ordering |

Position is also polled automatically every **500 ms** and shown in the bottom bar.

### Spot Navigation
| Control | Description |
|---|---|
| Spot combo | Populated after Manual Select (S1, S2, …) |
| [Go] | Move to the selected spot |
| [Next Spot] | Move to the next unvisited spot in sequence |
| Next: Sx label | Shows which spot is next and progress (e.g. "Next: S2  (2/4)") |
| [Contact] | Start/stop the contact sequence |

### SFC Calibration ▼ (collapsible, read-only)
Displays the lab calibration constants from `spot_alignment.py`:

| Field | Value |
|---|---|
| SFC X/Y/Z | 153.0 / 83.0 / 156.0 mm |
| Approach Z | 161.0 mm |
| Ref stage X/Y | 212.5 / 206.1 mm |
| Pixel scale | 0.095 mm/px |

Edit these in `device_drivers/spot_alignment.py` when the setup is re-calibrated.

### Alignment Options ▼ (collapsible)
| Control | Description |
|---|---|
| Dry Run | Compute and log steps, but do NOT move the stage |
| Flip X | Invert X axis direction (if stage moves wrong way) |
| Flip Y | Invert Y axis direction |
| Safety limit (mm) | Warn if computed XY move exceeds this (default 10 mm) |

---

## Bottom Bar

| Section | Description |
|---|---|
| **Force Sensor** | `ForceSensorDisplay` — shows live force reading (N) with ↑↓ arrows. Launches a serial bridge subprocess to read from the sensor. |
| **Stage Position** | X / Y / Z in mm, refreshed every 500 ms by a QTimer. |
| **Log** | Scrollable `QTextEdit` with `[INFO]` / `[WARN]` / `[ERROR]` prefixed lines. |

---

## Architecture & File Layout

### What actually runs

```
python main.py
  └── main.py  (2199 lines)
        ├── SpotAnalysisWorker (QThread) — runs run_spot_analysis() off UI thread
        ├── WeGptWorker        (QThread) — runs GPT_Merge.analyze_plate_and_spots() (unused — no button wired)
        ├── SpotAlignmentWorker(QThread) — executes MotionStep list from SpotAligner
        ├── ManualSpotDialog   (QDialog) — interactive spot-picker on top of image
        ├── ForceSensorDisplay (QWidget) — force sensor readout via QProcess bridge
        ├── ContactWorker      (QThread) — Z-approach loop with force threshold
        └── SimpleStageApp     (QMainWindow) — the full application
```

> **Note:** `gui/app_window.py` and `gui/widgets/` exist in the repo but are **not used** by `main.py`. They are a cleaner refactored version that was never wired up as the entry point.

### Device drivers
```
device_drivers/
├── GPT_Merge.py                  ← Plate + spot detection (used by main.py)
├── GPT_Merge_v2.py               ← Not used anywhere
├── GPT_Merge_v3.py               ← Used by gui/app_window.py (which isn't the entry point)
├── thorlabs_camera_wrapper.py    ← pylablib wrapper: snap/live/settings
├── plate_finder.py               ← HSV segmentation → movement hint string
├── plate_auto_adjuster.py        ← Closed-loop centering (≤10 iterations)
├── spot_alignment.py             ← Pixel→stage coordinate mapping + Z-safe sequences
├── image_utils.py                ← load_image / save_image / bgr_to_rgb
├── check_ports.py                ← Standalone serial-port utility (not imported)
└── spot_analysis/
    ├── pipeline.py               ← Public API: run_spot_analysis()
    ├── detection.py              ← Preprocessing + contour-based spot detection
    ├── inspection.py             ← Per-spot defect scoring (MAD / quantile)
    ├── visualization.py          ← Accept/reject overlay images
    ├── excel_export.py           ← spot_results.xlsx (openpyxl)
    └── config.py                 ← All tunable detection constants
```

### PI Control System
```
device_drivers/PI_Control_System/
├── app_factory.py               ← create_services(use_mock) — wires everything
├── core/models.py               ← Frozen dataclasses: Axis, Position, states
├── core/hardware/interfaces.py  ← AxisController ABC
├── hardware/pi_manager.py       ← Coordinates 3 axes; Z→X→Y reference order
├── hardware/pi_controller.py    ← Real pipython implementation
├── hardware/mock_controller.py  ← Deterministic mock for tests
├── services/event_bus.py        ← Thread-safe pub/sub
├── services/connection_service.py
├── services/motion_service.py   ← Moves, safe Z-ordering, motion sequences
└── config/                      ← 7-layer merge: defaults.json → env vars
```

### Threading model
| Thread | What runs |
|---|---|
| Main (Qt event loop) | All GUI rendering, QTimer live view (~100 ms), QTimer position poll (500 ms) |
| `ThreadPoolExecutor` (4 × "PIControl") | All blocking PI hardware I/O (USB, reference moves, motor waits) |
| `SpotAnalysisWorker` (QThread) | `run_spot_analysis()` — can take seconds on large images |
| `SpotAlignmentWorker` (QThread) | Executes `MotionStep` list for spot-to-spot moves |
| `ContactWorker` (QThread) | Z-approach loop; reads force; posts `step_done` signals |
| `ForceSensorDisplay` via QProcess | Serial bridge subprocess for force sensor |

---

## Hardware Requirements

| Item | Details |
|---|---|
| PI C-863 Mercury | 3 units (X, Y, Z axes). USB-serial. |
| Thorlabs CS165CU | USB3 scientific camera. Requires Thorlabs ThorCam SDK DLLs. |
| Force sensor | Connected via serial (default COM4). Bridge script at `ForceSensor/`. |
| Windows 10/11 | `os.add_dll_directory()` is Windows-only. |

> Run with `use_mock=True` (edit `main()` at bottom of `main.py`) for testing without hardware.

---

## Installation

```bash
pip install -r requirements.txt
```

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

**DLLs (Windows only)**
- PI GCS2 DLLs → `lib/pi_dlls/`
- Thorlabs ThorCam SDK → `C:\Program Files\Thorlabs\ThorImageCAM\Bin` (hardcoded in `main.py` line 645)

---

## How to Run

```bash
python main.py
```

`main.py` sets PI DLL paths on `os.add_dll_directory` and `PATH` **before any imports**, then launches `SimpleStageApp(use_mock=False)`.

To run without hardware, change the bottom of `main.py`:
```python
window = SimpleStageApp(use_mock=True)
```

---

## Vision Pipeline Details

### Plate detection (`GPT_Merge.analyze_plate_and_spots`)
Used by "Detect Plate". Returns:
- `plate_detected` (bool)
- `plate_bbox` (bounding box)
- `plate_image` (cropped BGR array)
- `all_spots`, `accepted_spots`, `rejected_spots`
- `error` (string or None)

### Spot analysis (`spot_analysis.pipeline.run_spot_analysis`)
Used by "Detect Spots". Full pipeline:

| Step | Module | What happens |
|---|---|---|
| Load | `pipeline.py` | Read image with OpenCV |
| Grayscale + background normalise | `detection.py` | Large-kernel Gaussian blur → divide-normalise to remove uneven lighting |
| CLAHE | `detection.py` | Local contrast enhancement |
| Adaptive threshold | `detection.py` | Binarise with adaptive block size |
| Morph open/close | `detection.py` | Remove noise, fill gaps |
| Contour filter | `detection.py` | Area, circularity ≥ 0.45, solidity ≥ 0.65, diameter ≥ 1.5 mm |
| Grid sort + label | `detection.py` | Row-major → A1, A2, B1, B2, … |
| Defect inspection | `inspection.py` | MAD outlier test + dark/bright quantile test per spot |
| Visualise | `visualization.py` | Green (accept) / red (reject) overlay |
| Excel export | `excel_export.py` | `spot_results.xlsx` with per-spot metrics |

Saves 10 debug images to `artifacts/we_detection/` (see [Output Artifacts](#output-artifacts)).

---

## Spot Analysis Module

Callable independently of the GUI:

```python
from device_drivers.spot_analysis.pipeline import run_spot_analysis

result = run_spot_analysis(
    image_path="path/to/plate.png",
    output_dir="artifacts/we_detection",
    export_excel=True,
)
```

Returned dict keys:

| Key | Type | Description |
|---|---|---|
| `all_spots` | `list[dict]` | All accepted candidate spots |
| `accepted_spots` | `list[dict]` | Spots with no defects |
| `rejected_spots` | `list[dict]` | Defective spots |
| `rejected_candidates` | `list[dict]` | Contours filtered out during detection |
| `overlay_image` | `np.ndarray` | BGR accept/reject colour overlay |
| `accepted_labels` | `list[str]` | e.g. `["A1", "A2"]` |
| `rejected_labels` | `list[str]` | e.g. `["B1"]` |
| `missing_spots` | `list[str]` | Expected grid positions that are absent |
| `per_spot_metrics` | `dict` | `{label: metrics_dict}` |
| `excel_path` | `str \| None` | Path to saved `.xlsx` |
| `error` | `str \| None` | Non-fatal error |

Tunable constants in `device_drivers/spot_analysis/config.py`:
```python
DEFAULT_MIN_SPOT_AREA        = 450       # px²
DEFAULT_MAX_SPOT_AREA        = 15000     # px²
DEFAULT_MIN_CIRCULARITY      = 0.45
DEFAULT_MIN_SOLIDITY         = 0.65
DEFAULT_PLATE_WIDTH_MM       = 50.0      # physical plate width
DEFAULT_MIN_SPOT_DIAMETER_MM = 1.5       # minimum spot diameter (mm)
DEFAULT_MAD_K                = 4.5       # MAD outlier multiplier
DEFAULT_MAX_OUTLIER_FRAC     = 0.16
DEFAULT_DEFECT_AREA_FRAC     = 0.03
```

---

## Spot Alignment (Pixel → Stage)

`device_drivers/spot_alignment.py` converts pixel coordinates from `ManualSpotDialog` into absolute stage XY targets and builds Z-safe motion sequences.

**Lab calibration constants** (edit here when re-calibrated):

| Constant | Value | Meaning |
|---|---|---|
| `PIXEL_SCALE_MM` | 0.095 mm/px | Physical scale per pixel |
| `SFC_X/Y/Z` | 153.0 / 83.0 / 156.0 mm | Absolute stage position of SFC opening |
| `APPROACH_Z` | 161.0 mm | Z stop height (SFC_Z + 5 mm) — approach only, never go to SFC_Z here |
| `REF_STAGE_X/Y` | 212.5 / 206.1 mm | Stage position when the reference image was taken |

**Z-safety rules enforced by `SpotAligner`:**
1. Never move Z down before XY alignment is complete.
2. Always raise Z before moving between spots.
3. Always stop at `APPROACH_Z` — never descend to `SFC_Z`.
4. Never go directly spot-to-spot without lifting Z.

---

## Output Artifacts

| Path | Contents |
|---|---|
| `artifacts/captures/` | Raw captured images (`Photo_<exp>_<gain>_<r>_<g>_<b>.png`) |
| `artifacts/plate_detection/` | Cropped plate image (`plate.png`) + any detection overlays |
| `artifacts/we_detection/` | 10 debug images + `spot_results.xlsx` |
| `artifacts/manual_spots/` | Annotated spot image + Excel from ManualSpotDialog |

Debug image sequence from `run_spot_analysis()`:
```
01_original.png
02_gray_raw.png
03_bg.png
04_gray_norm.png
05_blur.png
06_thresh_bw.png
07_opened.png
08_closed.png
09_rejected_candidates_overlay.png   ← yellow: filtered-out contours
10_accept_reject_overlay.png         ← green: ok / red: defective
```

---

## Configuration

There is no `app_config.yaml` in the current codebase. Configuration is either hardcoded in `main.py` or read from the PI Control System config chain.

**PI stage config (7-layer merge):**
1. Built-in `defaults.json`
2. User local overrides
3. Environment variable `PI_STAGE_CONFIG_PATH`

**PI stage CLI:**
```bash
python -m device_drivers.PI_Control_System.config show
python -m device_drivers.PI_Control_System.config set --park-position X=200.0 Y=200.0 Z=200.0
```

**Thorlabs DLL path** — hardcoded at `main.py:645`:
```python
TL_DLL_DIR = r"C:\Program Files\Thorlabs\ThorImageCAM\Bin"
```

---

## Testing

All 123 tests run without hardware (uses `MockAxisController` via dependency injection):

```bash
# Run all tests
pytest device_drivers/PI_Control_System/tests/ -v

# Single module
pytest device_drivers/PI_Control_System/tests/test_motion_service.py -v

# With coverage
pytest --cov=device_drivers device_drivers/PI_Control_System/tests/
```

---

## Key Design Decisions

| Decision | Reason |
|---|---|
| **`main.py` is monolithic** | All UI logic, workers, and dialogs live in one file. `gui/app_window.py` and `gui/widgets/` are a parallel refactor that was never switched to as the entry point. |
| **DLL paths before imports** | `pipython` and pylablib load DLLs at import time; path must be set first — done at top of `main.py` before any hardware imports. |
| **Connect && Initialize combined** | In practice these always run together; the separate `on_connect_clicked`/`on_initialize_clicked` methods still exist internally and are called in sequence. |
| **Frozen dataclasses** for all models | Thread safety via immutability — no locks needed for read-only state. |
| **Safe Z-ordering** in `MotionService` | When lowering Z: move XY first. When raising Z: lift Z first. Prevents collisions. |
| **PI reference sequence: Z first** | Physical safety constraint of this stage configuration. |
| **`SpotAlignmentWorker`** | Motion sequences can block for seconds; must not freeze the GUI. |
| **`ContactWorker`** | Z-approach loop; force threshold check runs in a thread to keep UI responsive. |
| **`ForceSensorDisplay` via QProcess** | Force sensor bridge runs as a subprocess so a crash doesn't take down the main app. |

---

## Dead / Unused Code

These exist in the repo but are not part of the active application:

| File / Directory | Status |
|---|---|
| `gui/app_window.py` + `gui/widgets/` | Parallel refactor — **not used** by `main.py` |
| `device_drivers/GPT_Merge_v2.py` | Superseded; not imported anywhere |
| `device_drivers/GPT_Merge_v3.py` | Only imported by `gui/app_window.py` (which isn't the entry point) |
| `device_drivers/check_ports.py` | Standalone serial-port utility; never imported |
| `generate_thesis_figures.py` | One-off script; not imported |
| `run_sensitivity.py` / `sensitivity_analysis.py` | Standalone analysis scripts; not imported by app |
| `test_detection_v2.py` | Comparison script; not in active code |
| `standard_plate.jpeg` | Not referenced in any `.py` file |
| `PI_XYZ-OOP/` | Duplicate PI control system; only `device_drivers/PI_Control_System/` is used |
| `on_we_gpt_clicked()` in `main.py` | Handler exists but no button is wired to it in the toolbar |
| `WeGptWorker` in `main.py` | Worker class for the above; unused at runtime |
