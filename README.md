# CTA – Computational Testing Apparatus

A laboratory automation desktop application for controlling a 3-axis PI motion stage, capturing images with a Thorlabs camera, detecting electrochemical plates, and analysing working-electrode spots for defects (bubbles, holes, non-uniformity).

---

## Table of Contents

1. [Overview](#overview)
2. [Architecture](#architecture)
3. [Project Structure](#project-structure)
4. [Hardware Requirements](#hardware-requirements)
5. [Software Requirements & Dependencies](#software-requirements--dependencies)
6. [How to Run](#how-to-run)
7. [Application UI Layout](#application-ui-layout)
8. [Button-by-Button Walkthrough](#button-by-button-walkthrough)
   - [Connect](#1-connect)
   - [Initialize](#2-initialize)
   - [Camera](#3-camera-startlive)
   - [Capture](#4-capture)
   - [Plate Detect](#5-plate-detect)
   - [Auto Adjust](#6-auto-adjust)
   - [WE Detect](#7-we-detect)
9. [Camera Settings Panel](#camera-settings-panel)
10. [Stage Control Panel](#stage-control-panel)
11. [Full File Reference](#full-file-reference)
    - [main.py](#mainpy)
    - [device_drivers/image_utils.py](#device_driversimage_utilspy)
    - [device_drivers/GPT_Merge.py](#device_driversgpt_mergepy)
    - [device_drivers/spot_analysis/](#device_driversspot_analysis)
    - [device_drivers/thorlabs_camera_wrapper.py](#device_driversthorldabs_camera_wrapperpy)
    - [device_drivers/plate_finder.py](#device_driversplate_finderpy)
    - [device_drivers/plate_auto_adjuster.py](#device_driversplate_auto_adjusterpy)
    - [device_drivers/PI_Control_System/](#device_driverspi_control_system)
12. [Output Artifacts](#output-artifacts)
13. [Configuration](#configuration)

---

## Overview

CTA integrates three physical subsystems into a single PySide6 GUI:

| Subsystem | Purpose |
|---|---|
| **PI XYZ Stage** | Nanometre-precision motion stage (3 axes, USB-serial) |
| **Thorlabs Camera** | Scientific camera for image acquisition |
| **Image Analysis** | OpenCV-based plate finding, spot detection, and defect inspection |

The typical workflow is:

```
Connect → Initialize → Camera Live → Capture → Plate Detect → Auto Adjust → WE Detect
```

---

## Architecture

The codebase follows a strict three-layer separation:

```
┌────────────────────────────────────────┐
│   main.py  (GUI only – no OpenCV)      │
│   SpotAnalysisWorker (QThread)         │
└────────────┬───────────────────────────┘
             │
┌────────────▼───────────────────────────┐
│   device_drivers/spot_analysis/        │
│     pipeline.py  ← public API          │
│     detection.py                       │
│     inspection.py                      │
│     visualization.py                   │
│     excel_export.py                    │
│     config.py  ← all tuning constants  │
└────────────┬───────────────────────────┘
             │
┌────────────▼───────────────────────────┐
│   device_drivers/  (hardware drivers)  │
│     PI_Control_System/                 │
│     thorlabs_camera_wrapper.py         │
│     plate_finder.py                    │
│     plate_auto_adjuster.py             │
│     GPT_Merge.py  (plate detection)    │
│     image_utils.py (I/O helpers)       │
└────────────────────────────────────────┘
```

**Key design rules:**
- `main.py` never imports `cv2` or `numpy` directly.  All OpenCV I/O goes through `device_drivers/image_utils.py`.
- `WE Detect` runs in a `QThread` (`SpotAnalysisWorker`) so the UI stays responsive during analysis.
- All detection tuning constants live exclusively in `device_drivers/spot_analysis/config.py`.
- All output files are written under `artifacts/`.

---

## Project Structure

```
CTA/
├── main.py                                  # Application entry point – GUI only
├── requirements.txt                         # Python dependencies
│
├── device_drivers/
│   ├── image_utils.py                       # load_image / save_image / bgr_to_rgb (no cv2 in main.py)
│   ├── GPT_Merge.py                         # Plate bounding-box detector (used by Plate Detect)
│   ├── plate_finder.py                      # Gray-plate-on-red-background detector
│   ├── plate_auto_adjuster.py               # Feedback loop: capture → detect → move stage
│   ├── thorlabs_camera_wrapper.py           # Thorlabs camera connect/capture/settings
│   ├── we_detection.py                      # Legacy file – NOT used anywhere in the app
│   │
│   ├── spot_analysis/                       # Modular spot analysis pipeline (WE Detect)
│   │   ├── __init__.py
│   │   ├── config.py                        # ALL tuning constants – edit here to tune
│   │   ├── detection.py                     # Spot detection, sort_and_label, find_missing_spots
│   │   ├── inspection.py                    # Per-spot defect inspection (MAD-based)
│   │   ├── visualization.py                 # Colour-coded contour overlays
│   │   ├── excel_export.py                  # Export results to .xlsx
│   │   └── pipeline.py                      # run_spot_analysis() – public entry point
│   │
│   └── PI_Control_System/
│       ├── app_factory.py                   # Wires all PI services together
│       ├── config/
│       │   ├── defaults.json                # COM ports, serial numbers, travel ranges
│       │   └── loader.py                    # Reads defaults.json into Python objects
│       ├── core/
│       │   └── models.py                    # Axis enum, Position, ConnectionState, etc.
│       ├── hardware/
│       │   ├── pi_controller.py             # Real PIAxisController (pipython)
│       │   ├── mock_controller.py           # Simulated MockAxisController for testing
│       │   └── pi_manager.py               # PIControllerManager – holds all 3 axis controllers
│       ├── services/
│       │   ├── event_bus.py                 # Pub/sub event bus
│       │   ├── connection_service.py        # Connect / initialize / shutdown logic
│       │   └── motion_service.py            # move_to, jog, absolute move (all async)
│       └── gui/
│           └── main_window.py               # Legacy standalone PI GUI (not used in CTA)
│
├── artifacts/                               # All output images and Excel files
│   ├── captures/                            # Raw captured images from camera
│   ├── plate_detection/                     # Cropped plate images from Plate Detect
│   ├── we_detection/                        # overlay.png + spot_results.xlsx from WE Detect
│   └── auto_adjust/                         # Per-iteration images from Auto Adjust loop
│
└── config/                                  # Reserved for future app-level config
```

---

## Hardware Requirements

| Hardware | Details |
|---|---|
| **PI Linear Stage – X axis** | COM5, baud 115200, serial `025550131`, stage model `62309260` |
| **PI Linear Stage – Y axis** | COM3, baud 115200, serial `025550143`, stage model `62309260` |
| **PI Linear Stage – Z axis** | COM4, baud 115200, serial `025550149`, stage model `62309260` |
| **Thorlabs TL Camera** | Any camera supported by the Thorlabs TL SDK; DLL must be in `C:\Program Files\Thorlabs\ThorImageCAM\Bin` |

Travel ranges:
- X: 5 – 200 mm
- Y: 0 – 200 mm
- Z: 15 – 200 mm

Park position (post-initialization): **200 mm on all axes**

Reference mode for all axes: **FPL** (Forward Position Limit)

---

## Software Requirements & Dependencies

```
PySide6        # GUI framework
opencv-python  # Image processing (cv2)
numpy          # Numerical operations
openpyxl       # Excel export (.xlsx)
pipython       # PI GCS2 controller communication
pylablib       # Thorlabs TL camera SDK wrapper
```

Install with:

```bash
pip install -r requirements.txt
```

The Thorlabs TL camera SDK DLLs (`thorlabs_tsi_camera_sdk`, `thorlabs_unified_sdk`) must also be installed on the system.  The PI GCS2 DLL files (`PI_GCS2_DLL.dll`, `E816_DLL.dll`) must be present in the project root directory.

---

## How to Run

```bash
python main.py
```

The application starts with `use_mock=False`, meaning it expects real PI controllers and a real Thorlabs camera.  If the hardware is absent the app still launches — camera absence falls back to a file-picker, and stage errors are shown in message boxes.

To run with simulated (mock) hardware for development/testing, change the last lines of `main.py`:

```python
window = SimpleStageApp(use_mock=True)
```

---

## Application UI Layout

```
┌─────────────────────────────────────────────────────────────────────┐
│  ● STATUS   [Connect] [Initialize] [Camera] [Capture]               │
│             [Plate Detect] [Auto Adjust] [WE Detect]                │
├────────────────────────┬────────────────────────────────────────────┤
│  Camera Settings       │                                            │
│  ─────────────────     │                                            │
│  Exposure (ms): [    ] │         Image Display Area                 │
│  Gain (dB):     [    ] │         (800 × 500 px minimum)            │
│  White Balance: [▼   ] │         Live / Captured / Processed        │
│  R: [ ] G: [ ] B: [ ] │                                            │
│  [Apply White Balance] │                                            │
│                        │                                            │
│  Stage Control         │                                            │
│  ─────────────────     │                                            │
│  Position: X Y Z       │                                            │
│  Step(mm): [   ] [↻]   │                                            │
│  X: [−] [+]            │                                            │
│  Y: [−] [+]            │                                            │
│  Z: [−] [+]            │                                            │
│  Go to: X[ ] Y[ ] Z[ ] │                                            │
│  [Go]                  │                                            │
├────────────────────────┴────────────────────────────────────────────┤
│  Log                                                                │
│  [INFO] ...                                                         │
└─────────────────────────────────────────────────────────────────────┘
```

---

## Button-by-Button Walkthrough

### 1. Connect

**Button:** `Connect`
**Handler:** `SimpleStageApp.on_connect_clicked()` — `main.py`

**What it does:**

Establishes serial USB connections to all three PI motion controllers (X, Y, Z).

**Execution flow:**

1. Sets status to yellow `CONNECTING...`
2. Calls `self.connection_service.connect()` — async, returns a `Future`.
3. Blocks `.result(timeout=30)` until connection resolves.
4. On success: status turns `CONNECTED`.
5. On failure: status turns `ERROR`, a critical message box is shown.

**Files involved:**

| File | Role |
|---|---|
| `main.py` | Button handler, status update, error dialog |
| `device_drivers/PI_Control_System/services/connection_service.py` | `connect()` — dispatches to thread executor |
| `device_drivers/PI_Control_System/hardware/pi_manager.py` | `PIControllerManager` — iterates over all 3 axis controllers |
| `device_drivers/PI_Control_System/hardware/pi_controller.py` | `PIAxisController.connect()` — opens GCSDevice over COM port |
| `device_drivers/PI_Control_System/config/defaults.json` | COM ports, baud rates, serial numbers |
| `device_drivers/PI_Control_System/core/models.py` | `ConnectionState` enum |
| `device_drivers/PI_Control_System/services/event_bus.py` | Publishes `CONNECTION_STARTED`, `CONNECTION_SUCCEEDED` |

---

### 2. Initialize

**Button:** `Initialize`
**Handler:** `SimpleStageApp.on_initialize_clicked()` — `main.py`

**What it does:**

References (homes) all three axes so the controller knows absolute positions, then moves the stage to the park position (200, 200, 200 mm).

**Execution flow:**

1. Checks `connection_service.state.connection == CONNECTED`; warns if not.
2. Sets status to `INITIALIZING...`
3. Calls `connection_service.initialize()` — blocks up to 120 s (stage moves to limit switch).
4. Sets status to `PARKING...`
5. Calls `motion_service.move_to_position_safe_z(Position(200, 200, 200))`.
   - Safe-Z: Z moves first when going higher, last when going lower.
6. On success: status turns `READY`.

**Referencing order** (from `defaults.json`): Z → X → Y

**Files involved:**

| File | Role |
|---|---|
| `main.py` | Handler, park position, status updates |
| `device_drivers/PI_Control_System/services/connection_service.py` | `initialize()` — FPL homing per axis |
| `device_drivers/PI_Control_System/hardware/pi_controller.py` | `reference()` — GCS FPL command |
| `device_drivers/PI_Control_System/services/motion_service.py` | `move_to_position_safe_z()` |
| `device_drivers/PI_Control_System/core/models.py` | `Position` dataclass |
| `device_drivers/PI_Control_System/config/defaults.json` | `park_position`, `reference_order` |

---

### 3. Camera (Start / Live)

**Button:** `Camera`
**Handler:** `SimpleStageApp.on_cam_start_clicked()` — `main.py`

**What it does:**

Toggles live camera preview at ~10 fps.

**Execution flow (Start):**

1. Connects camera if not already connected.
2. Starts `self.live_timer` (100 ms interval → ~10 fps).
3. Every 100 ms `_update_live_view()` fires:
   - Calls `camera.grab_frame()` → BGR `ndarray`.
   - Calls `_show_image(frame)` → `bgr_to_rgb()` + `QPixmap` → displayed in panel.

**Execution flow (Stop):**

1. Stops the timer; resets button text.

**Files involved:**

| File | Role |
|---|---|
| `main.py` | Toggle logic, QTimer, `_update_live_view()`, `_show_image()` |
| `device_drivers/thorlabs_camera_wrapper.py` | `connect()`, `grab_frame()` |
| `device_drivers/image_utils.py` | `bgr_to_rgb()` — converts for Qt display |

**`grab_frame()` detail** (`thorlabs_camera_wrapper.py`):

- `self._cam.snap()` (pylablib) acquires one frame.
- If `uint16`: normalises per-channel to 0–255.
- If 2D (grayscale): converts to BGR.
- Applies software white balance via `_apply_white_balance()`.
- Returns BGR `uint8` `ndarray`.

---

### 4. Capture

**Button:** `Capture`
**Handler:** `SimpleStageApp.on_capture_clicked()` — `main.py`

**What it does:**

Takes a still image. Camera path saves the frame to disk. No-camera path opens a file picker.

**Execution flow:**

1. Tries to connect camera if not already connected.
2. **Camera available** (`_capture_from_camera()`):
   - Builds filename from exposure/gain/WB: `Photo_{exp}_{gain}_{R}_{G}_{B}.png`.
   - Finds a unique filename if needed.
   - `camera.save_frame(filename)` → captures and writes PNG.
   - Stores path in `self.last_image_path`.
   - Calls `_show_image(frame)`.
3. **No camera** (`_capture_from_file()`):
   - Warns in log.
   - Opens `QFileDialog.getOpenFileName`.
   - `load_image(path)` reads the file (via `image_utils.py`).
   - Stores path in `self.last_image_path`.
   - Calls `_show_image(img)`.

**Files involved:**

| File | Role |
|---|---|
| `main.py` | Handler, filename construction, `_capture_from_camera()`, `_capture_from_file()` |
| `device_drivers/thorlabs_camera_wrapper.py` | `connect()`, `save_frame()` |
| `device_drivers/image_utils.py` | `load_image()` — reads file in no-camera path |

**Output:** `artifacts/captures/Photo_<exp>_<gain>_<R>_<G>_<B>[_N].png`

---

### 5. Plate Detect

**Button:** `Plate Detect`
**Handler:** `SimpleStageApp.on_plate_clicked()` — `main.py`

**What it does:**

Finds the electrochemical plate bounding box in the captured image and saves the cropped plate for WE Detect.

**Execution flow:**

1. Uses `self.last_image_path`; prompts file picker if None.
2. Calls `analyze_plate_and_spots(image_path, save_dir)` from `GPT_Merge.py`.
3. On error / no plate detected: shows warning dialog.
4. Calls `save_image(plate_path, plate_img)` (via `image_utils.py`) to write `plate.png`.
5. Stores `plate_path` in `self.last_plate_path` for WE Detect.
6. Calls `_show_image(plate_img)`.

**`analyze_plate_and_spots()` detail** (`GPT_Merge.py`):

1. `cv2.imread` → load image.
2. `resize_image(img, resize_percent)` → full resolution (100%).
3. `detect_plate(img)`:
   - Grayscale → `GaussianBlur` (3×3) → `Canny` (45, 40) → `dilate`.
   - `findContours` external → largest contour → `boundingRect`.
4. Crop plate region.
5. `detect_spots(plate)`:
   - Grayscale → `GaussianBlur` (5×5).
   - `adaptiveThreshold` (Gaussian, blockSize=49, C=3).
   - `morphologyEx` MORPH_OPEN (3×3).
   - Filter by area (100–15,000 px²) and circularity (≥ 0.2).
6. `sort_and_label(spots)` → labels A1, A2, B1, B2, …
7. `compute_inspection_radius(spots)` → `r_check = 3 × (min_radius / 4)`.
8. `has_bubble_or_hole(gray, spot, r_check)`:
   - **Bubble:** coefficient of variation `std/mean > 0.3`.
   - **Hole:** Otsu threshold + RETR_CCOMP; any contour with a parent → hole.
9. Saves `all_detected.png` and `accepted_only.png`.
10. Returns full result dict.

**Files involved:**

| File | Role |
|---|---|
| `main.py` | Handler, file picker, path storage, display |
| `device_drivers/GPT_Merge.py` | `analyze_plate_and_spots()` — full plate pipeline |
| `device_drivers/image_utils.py` | `save_image()` — writes plate.png |

**Output:** `artifacts/plate_detection/plate.png`

---

### 6. Auto Adjust

**Button:** `Auto Adjust`
**Handler:** `SimpleStageApp.on_adjust_clicked()` — `main.py`

**What it does:**

Closed-loop feedback loop: capture → detect plate position → move stage → repeat until centred or max iterations reached.

**Execution flow:**

1. Checks `_is_stage_ready()`.
2. Connects camera if needed.
3. Calls `auto_adjust_plate(motion_service, camera, save_dir, step_mm=5.0, max_iterations=10)`.
4. Logs all `steps_log` messages.
5. Shows success or warning dialog.

**`auto_adjust_plate()` detail** (`plate_auto_adjuster.py`):

For each iteration (up to 10):
1. `camera.save_frame(img_path)` → `artifacts/auto_adjust/auto_adjust_{i}.png`.
2. `gray_plate_on_red(img_path, margin_frac=0.02)`:
   - HSV conversion → two red-hue masks (0–10° and 170–180°) → combined.
   - Morphological close (5×5, 2 iterations).
   - Largest red contour → `red_bbox`.
   - Inverted mask → threshold dark regions → 4-corner polygon filter.
   - Checks if plate bbox is inside red bbox with 2% margin on each side.
   - Computes direction hint: `"left"`, `"right"`, `"up"`, `"down"`, or compound.
3. If `fully_in_frame` → success.
4. Maps hint to `move_axis_relative(X or Y, ±step_mm)`.
5. Waits for futures before next iteration.

**Files involved:**

| File | Role |
|---|---|
| `main.py` | Handler, stage-ready check, log output |
| `device_drivers/plate_auto_adjuster.py` | `auto_adjust_plate()` — feedback loop |
| `device_drivers/plate_finder.py` | `gray_plate_on_red()` — HSV plate visibility check |
| `device_drivers/thorlabs_camera_wrapper.py` | `save_frame()` per iteration |
| `device_drivers/PI_Control_System/services/motion_service.py` | `move_axis_relative()` |

**Output:** `artifacts/auto_adjust/auto_adjust_N.png` + `*_checked.png` per iteration.

---

### 7. WE Detect

**Button:** `WE Detect`
**Handler:** `SimpleStageApp.on_we_clicked()` — `main.py`

**What it does:**

Runs the full modular spot analysis pipeline in a **background thread** so the UI stays responsive.  Each spot is inspected for defects; results are colour-coded (blue = good, red = bad) and exported to Excel.

**Execution flow:**

1. Uses `self.last_plate_path`; prompts file picker if None.
2. Disables the `WE Detect` button and labels it `"WE Detect (running…)"`.
3. Creates `SpotAnalysisWorker(image_path, save_dir)` (`QThread`).
4. Connects `worker.finished` → `_on_we_finished()` and `worker.error` → `_on_we_error()`.
5. Calls `worker.start()` — analysis runs in background.
6. UI remains fully responsive (can jog stage, change exposure, etc.).
7. On completion `_on_we_finished(result)` fires on the UI thread:
   - Displays overlay image.
   - Logs: detected, accepted, rejected, rejected labels, missing spots, Excel path.
   - Shows information or warning dialog.

**`run_spot_analysis()` detail** (`spot_analysis/pipeline.py`):

1. `cv2.imread(image_path)` — raises `ValueError` if image cannot be loaded.
2. `detect_spots(img)` (`detection.py`):
   - `preprocess_for_detection(img)`:
     - BGR → grayscale.
     - Large `GaussianBlur` (kernel 81×81) → background estimate.
     - `cv2.divide(gray, bg, scale=255)` → normalise uneven lighting.
     - CLAHE (clipLimit=2.0, tileSize=8×8) → local contrast enhancement.
   - `GaussianBlur` (5×5) on normalised image.
   - `adaptiveThreshold` (Gaussian, blockSize=35, C=2, THRESH_BINARY_INV).
   - MORPH_OPEN (2×2 kernel) → remove noise.
   - MORPH_CLOSE (3×3 kernel) → fill gaps.
   - `findContours` external.
   - Accept contours with area ∈ [450, 15,000 px²], circularity ≥ 0.45, solidity ≥ 0.65.
   - Rejected candidates include a `reason` field (`"area"`, `"circularity"`, `"solidity"`).
3. For each accepted spot, `inspect_spot_defects(gray_norm, spot)` (`inspection.py`):
   - Draws filled contour mask.
   - Extracts pixel values under mask.
   - If < 80 pixels → not flagged (returns `False`).
   - Computes **median** and **MAD** (Median Absolute Deviation).
   - Modified Z-scores: `z = |val − median| / (1.4826 × MAD)`.
   - `outlier_frac = fraction of pixels with z > 4.5`.
   - If `outlier_frac > 0.16` → spot is `is_bad = True`, reason `"nonuniform"`.
4. `sort_and_label(spots)` (`detection.py`):
   - Sort by Y → group into rows using median-row-gap threshold.
   - Within each row sort by X.
   - Assign labels A1, A2, …, B1, B2, …
5. `find_missing_spots(spots)` (`detection.py`):
   - Builds row/column set from existing labels.
   - Determines expected rectangular grid extent.
   - Returns list of absent labels (e.g. `["A3", "B2"]`).
6. `draw_accept_reject_overlay(img, spots)` (`visualization.py`):
   - Contours: **blue** = good, **red** = bad.
   - Center dot at centroid.
   - Label text next to centroid.
7. Saves `overlay.png` to output directory.
8. `export_results_to_excel(path, result)` (`excel_export.py`):
   - **Summary sheet:** Detected / Accepted / Rejected counts + accepted labels / rejected labels / missing spots rows.
   - **Spots sheet:** Per-spot table — Label, Status, Area, Circularity, Solidity.
9. Returns standardised result dict with all keys (see [Standardised Result Structure](#standardised-result-structure)).

**Standardised result structure** returned by `run_spot_analysis()`:

```python
{
    "all_spots":           list[dict],   # every accepted candidate
    "accepted_spots":      list[dict],   # spots with no defects
    "rejected_spots":      list[dict],   # defective spots
    "rejected_candidates": list[dict],   # contours filtered at detection stage
    "overlay_image":       np.ndarray,   # BGR colour-coded image
    "accepted_labels":     list[str],    # e.g. ["A1", "A2", "B1"]
    "rejected_labels":     list[str],    # e.g. ["B3"]
    "missing_spots":       list[str],    # e.g. ["A3"]
    "excel_path":          str | None,   # path to saved .xlsx
    "error":               str | None,   # non-fatal error, e.g. Excel failure
}
```

**Files involved:**

| File | Role |
|---|---|
| `main.py` | Handler, `SpotAnalysisWorker` (QThread), `_on_we_finished()`, `_on_we_error()` |
| `device_drivers/spot_analysis/pipeline.py` | `run_spot_analysis()` — public entry point |
| `device_drivers/spot_analysis/detection.py` | `detect_spots()`, `sort_and_label()`, `find_missing_spots()` |
| `device_drivers/spot_analysis/inspection.py` | `inspect_spot_defects()` — MAD-based outlier test |
| `device_drivers/spot_analysis/visualization.py` | `draw_accept_reject_overlay()` |
| `device_drivers/spot_analysis/excel_export.py` | `export_results_to_excel()` |
| `device_drivers/spot_analysis/config.py` | All tuning constants |

**Output:**
- `artifacts/we_detection/overlay.png` — colour-coded spot overlay
- `artifacts/we_detection/spot_results.xlsx` — Excel report

**Log output example:**
```
[INFO] WE detection using plate image: artifacts/plate_detection/plate.png
[INFO] Detected spots:  12
[INFO] Accepted:        11
[WARN] Rejected:        1
[WARN] Rejected labels: B3
[WARN] Missing spots:   A3
[INFO] Excel saved:     artifacts/we_detection/spot_results.xlsx
```

---

## Camera Settings Panel

All controls are in `main.py` — the camera settings group.

### Exposure

- **Spinbox:** `spin_exposure` — range 1.0–5,000.0 ms, default 100 ms.
- **Set button → `on_set_exposure()`:**
  - Reads `spin_exposure.value()`, divides by 1000 (ms → sec).
  - Calls `self.camera.set_exposure(exposure_sec)`.
  - In `thorlabs_camera_wrapper.py`: forwards to pylablib `set_exposure()`.

### Gain

- **Spinbox:** `spin_gain` — range 0.0–48.0 dB, default 0.
- **Set button → `on_set_gain()`:**
  - Calls `self.camera.set_gain(gain)` → `self._cam.set_gain(gain)`.

### White Balance

- **Preset dropdown:** `combo_wb` — Default, Warm, Cool, Reduce NIR, Custom.
- **`on_wb_preset_changed(preset)`:** Updates R/G/B spinboxes then calls `on_apply_white_balance()`.

| Preset | R | G | B |
|---|---|---|---|
| Default | 1.0 | 1.0 | 1.0 |
| Warm | 1.0 | 0.9 | 0.7 |
| Cool | 0.9 | 1.0 | 1.2 |
| Reduce NIR | 0.6 | 0.8 | 1.0 |
| Custom | (unchanged) | | |

- **Apply button → `on_apply_white_balance()`:**
  - Calls `camera.set_white_balance(r, g, b)` → stores gains clamped to [0.1, 4.0].
  - Applied in `grab_frame()` via `_apply_white_balance()`:
    - Frame to `float32` → multiply each BGR channel by its gain → clip → `uint8`.

**Files involved:** `main.py`, `device_drivers/thorlabs_camera_wrapper.py`

---

## Stage Control Panel

### Position Display

- `pos_label` — monospace label showing current XYZ.
- **Refresh button → `on_refresh_position()`:** `motion_service.get_current_position()` → updates label and goto spinboxes.

### Jog (Relative Move)

- Six buttons: `±X`, `±Y`, `±Z`.
- **`on_jog_axis(axis, direction)`:**
  - `step = spin_step.value() × direction`.
  - `motion_service.move_axis_relative(axis, step).result(timeout=30)`.
  - Refreshes position display.

### Absolute Move (Go To)

- Three spinboxes: 0–300 mm.
- **Go button → `on_goto_position()`:**
  - Builds `Position(x, y, z)`.
  - `motion_service.move_to_position_safe_z(target).result(timeout=60)`.
  - Refreshes position display.

**Files involved:**

| File | Role |
|---|---|
| `main.py` | All panel UI and handlers |
| `device_drivers/PI_Control_System/services/motion_service.py` | `move_axis_relative()`, `move_to_position_safe_z()`, `get_current_position()` |
| `device_drivers/PI_Control_System/hardware/pi_controller.py` | Low-level GCS commands |
| `device_drivers/PI_Control_System/core/models.py` | `Axis` enum, `Position` dataclass |

---

## Full File Reference

### `main.py`

The single file that defines the entire GUI application (`SimpleStageApp(QMainWindow)`) and the background worker.

**No OpenCV or numpy imports at the module level.** All image I/O goes through `device_drivers/image_utils.py`.

| Class / Method | Description |
|---|---|
| `SpotAnalysisWorker(QThread)` | Background thread that calls `run_spot_analysis()` |
| `SpotAnalysisWorker.finished` | `Signal(dict)` — emits result on success |
| `SpotAnalysisWorker.error` | `Signal(str)` — emits error message on failure |
| `SimpleStageApp.__init__` | Constructs all UI widgets and wires signals |
| `log(message, level)` | Appends `[INFO]/[WARN]/[ERROR]` to the log panel |
| `set_status(status, state)` | Updates the coloured status indicator |
| `_show_image(img)` | Converts BGR ndarray → QPixmap and updates image panel |
| `_is_stage_ready()` | Returns True if stage is connected and initialized |
| `_pick_image_file(title)` | Opens file-picker dialog, returns path or None |
| `on_connect_clicked()` | Connects PI stage controllers |
| `on_initialize_clicked()` | References axes and parks stage |
| `on_cam_start_clicked()` | Toggles live camera view |
| `on_capture_clicked()` | Dispatches to camera or file-picker path |
| `_capture_from_camera()` | Saves frame from camera to captures/ |
| `_capture_from_file()` | Loads user-chosen image file |
| `on_plate_clicked()` | Runs plate detection via GPT_Merge |
| `on_adjust_clicked()` | Runs auto-adjust feedback loop |
| `on_we_clicked()` | Launches SpotAnalysisWorker thread |
| `_on_we_finished(result)` | UI callback: display overlay, log, show dialog |
| `_on_we_error(error_msg)` | UI callback: log error, show critical dialog |
| `on_set_exposure()` | Applies exposure spinbox value |
| `on_set_gain()` | Applies gain spinbox value |
| `on_wb_preset_changed(preset)` | Updates RGB spinboxes on preset selection |
| `on_apply_white_balance()` | Applies RGB gains to camera |
| `on_refresh_position()` | Reads and displays current stage position |
| `on_jog_axis(axis, direction)` | Moves one axis by step size |
| `on_goto_position()` | Moves stage to absolute XYZ coordinates |
| `_update_live_view()` | Timer callback for live preview |
| `closeEvent(event)` | Disconnects hardware cleanly on exit |

---

### `device_drivers/image_utils.py`

Thin I/O layer that keeps `cv2` and `numpy` out of `main.py`.

| Function | Description |
|---|---|
| `load_image(path)` | `cv2.imread` wrapper — returns BGR ndarray or None |
| `save_image(path, img)` | `cv2.imwrite` wrapper — creates parent dirs, returns bool |
| `bgr_to_rgb(img)` | `cv2.cvtColor(BGR→RGB)` — used before Qt display |

---

### `device_drivers/GPT_Merge.py`

Unified plate + spot detection used by **Plate Detect**. Not used by WE Detect.

| Function | Description |
|---|---|
| `resize_image(img, percent)` | Resize by percentage using Lanczos |
| `detect_plate(image)` | Canny edge → largest contour → bounding rect |
| `detect_spots(plate_img, ...)` | Adaptive threshold → filter by area + circularity |
| `compute_inspection_radius(spots)` | `r_check = 3 × (min_radius / 4)` |
| `has_bubble_or_hole(gray, spot, r_check)` | CV-based bubble + Otsu topology hole check |
| `sort_and_label(spots)` | Sort into rows/columns, assign A1/B2/… labels |
| `draw_results(image, spots, px, py)` | Draw contours, centers, labels |
| `analyze_plate_and_spots(image_path, ...)` | **Main entry point** — returns full result dict |

---

### `device_drivers/spot_analysis/`

The modular spot analysis pipeline. Only this system is used for **WE Detect**.

#### `config.py`

All tuning constants. Edit here — never hardcode values in algorithm files.

| Constant | Value | Purpose |
|---|---|---|
| `DEFAULT_MIN_SPOT_AREA` | 450 px² | Minimum valid spot area |
| `DEFAULT_MAX_SPOT_AREA` | 15,000 px² | Maximum valid spot area |
| `DEFAULT_MIN_CIRCULARITY` | 0.45 | Minimum roundness |
| `DEFAULT_MIN_SOLIDITY` | 0.65 | Minimum solidity (area / convex hull area) |
| `DEFAULT_BG_BLUR_K` | 81 | Kernel size for background blur |
| `DEFAULT_CLAHE_CLIP` | 2.0 | CLAHE clip limit |
| `DEFAULT_CLAHE_TILE` | (8, 8) | CLAHE tile grid size |
| `DEFAULT_THRESH_BLOCKSIZE` | 35 | Adaptive threshold block size |
| `DEFAULT_THRESH_C` | 2 | Adaptive threshold C constant |
| `DEFAULT_OPEN_KERNEL` | 2 | Morphological open kernel size |
| `DEFAULT_CLOSE_KERNEL` | 3 | Morphological close kernel size |
| `DEFAULT_MAD_K` | 4.5 | Z-score threshold for outlier pixels |
| `DEFAULT_MAX_OUTLIER_FRAC` | 0.16 | Max outlier fraction before spot is flagged bad |
| `DEFAULT_DARK_Q` | 10 | 10th-percentile intensity reference |
| `DEFAULT_BRIGHT_Q` | 95 | 95th-percentile intensity reference |

#### `detection.py`

| Function | Description |
|---|---|
| `preprocess_for_detection(bgr)` | Grayscale → background subtraction → CLAHE |
| `detect_spots(image)` | Full detection pipeline → returns `(spots, rejected, debug)` |
| `sort_and_label(spots)` | Sort into rows/columns, assign A1/B2/… labels in-place |
| `find_missing_spots(labeled_spots)` | Compare present labels against expected grid → return missing label list |

#### `inspection.py`

| Function | Description |
|---|---|
| `inspect_spot_defects(gray, spot)` | Mask spot, extract pixels, compute MAD Z-scores, flag if outlier fraction > threshold |

#### `visualization.py`

| Function | Description |
|---|---|
| `draw_accept_reject_overlay(image, spots)` | Blue (good) / red (bad) contours + center dots + labels |

#### `excel_export.py`

| Function | Description |
|---|---|
| `export_results_to_excel(path, result)` | Write Summary sheet (counts + label lists + missing) and Spots sheet (per-spot metrics) |

#### `pipeline.py`

| Function | Description |
|---|---|
| `run_spot_analysis(image_path, output_dir, export_excel)` | Full pipeline: load → detect → inspect → label → find gaps → visualise → save → return dict |

---

### `device_drivers/thorlabs_camera_wrapper.py`

| Method | Description |
|---|---|
| `connect()` | Sets DLL path, opens first camera, sets default exposure/gain |
| `disconnect()` | Stops acquisition, closes camera |
| `grab_frame()` | `snap()` → normalise → handle grayscale → apply WB → return BGR ndarray |
| `save_frame(path)` | `grab_frame()` then `cv2.imwrite` |
| `set_exposure(sec)` | Forwards to pylablib |
| `set_gain(db)` | Forwards to pylablib |
| `set_white_balance(r, g, b)` | Stores clamped gains |
| `_apply_white_balance(frame)` | Multiplies BGR channels, clips to [0, 255] |

---

### `device_drivers/plate_finder.py`

| Function | Description |
|---|---|
| `gray_plate_on_red(image_path, margin_frac, debug)` | HSV red detection → non-red dark region → 4-corner filter → inside-check → direction hint |

Returns dict with keys: `rect_bbox`, `fully_in_frame`, `move_hint`, `output_image`, `save_path`.

`move_hint` values: `"ok"`, `"left"`, `"right"`, `"up"`, `"down"`, `"left_up"`, `"no_red"`, `"no_plate"`, `"adjust"`.

---

### `device_drivers/plate_auto_adjuster.py`

| Function | Description |
|---|---|
| `auto_adjust_plate(motion_service, camera, save_dir, step_mm, max_iterations)` | Capture → `gray_plate_on_red` → map hint to ΔX/ΔY → move stage → repeat |

Returns `(fully_in_frame: bool, final_hint: str, log_messages: list[str])`.

---

### `device_drivers/PI_Control_System/`

#### `app_factory.py`

| Function | Description |
|---|---|
| `create_services(use_mock)` | Loads config, creates executor, EventBus, 3 controllers, ConnectionService, MotionService |

#### `config/defaults.json`

Hardware configuration. Edit to change COM ports, serial numbers, velocity, park position.

#### `core/models.py`

| Class | Description |
|---|---|
| `Axis` | Enum: `X`, `Y`, `Z` |
| `Position` | Dataclass: `x`, `y`, `z` floats (mm) |
| `ConnectionState` | Enum: `DISCONNECTED`, `CONNECTING`, `CONNECTED`, `ERROR` |
| `InitializationState` | Enum: `NOT_INITIALIZED`, `INITIALIZING`, `INITIALIZED` |
| `AxisConfig` | Per-axis config: port, baud, serial, travel range, velocity |

#### `hardware/pi_controller.py`

`PIAxisController` wraps a `pipython.GCSDevice` for one physical controller.

| Method | Description |
|---|---|
| `connect()` | Opens GCS device over USB/serial |
| `reference()` | FPL homing command |
| `move_absolute(pos)` | GCS `MOV` |
| `move_relative(dist)` | GCS `MVR` |
| `get_position()` | GCS `qPOS` |

#### `hardware/mock_controller.py`

`MockAxisController` — identical interface, simulates motion in memory. Used when `use_mock=True`.

#### `services/connection_service.py`

All methods return `Future` objects (non-blocking).

| Method | Description |
|---|---|
| `connect()` | Dispatches `_connect_all()` to thread executor |
| `initialize()` | Dispatches `_initialize_all()` (references all axes) |
| `shutdown()` | Disconnects all controllers |
| `is_ready()` | True if both CONNECTED and INITIALIZED |

#### `services/motion_service.py`

All motion commands return `Future`.

| Method | Description |
|---|---|
| `move_to_position(target)` | Simultaneous XYZ move |
| `move_to_position_safe_z(target)` | Z-safe ordered move |
| `move_axis_relative(axis, distance)` | Jog one axis |
| `move_axis_absolute(axis, position)` | Move one axis to absolute position |
| `get_current_position()` | Returns current `Position` snapshot |

#### `services/event_bus.py`

Pub/sub system. Events: `CONNECTION_STARTED`, `CONNECTION_SUCCEEDED`, `STATE_CHANGED`, `MOTION_STARTED`, `MOTION_COMPLETED`, `ERROR`.

---

## Output Artifacts

All output files are written under `artifacts/` in the project root (created automatically).

| Directory | Created by | Contents |
|---|---|---|
| `artifacts/captures/` | Capture button | `Photo_<exp>_<gain>_<R>_<G>_<B>[_N].png` — raw frames |
| `artifacts/plate_detection/` | Plate Detect button | `plate.png` — cropped plate; `all_detected.png`, `accepted_only.png` |
| `artifacts/we_detection/` | WE Detect button | `overlay.png` — colour-coded spots; `spot_results.xlsx` — Excel report |
| `artifacts/auto_adjust/` | Auto Adjust button | `auto_adjust_N.png` per iteration; `*_checked.png` annotated copies |

---

## Configuration

### PI Stage — `device_drivers/PI_Control_System/config/defaults.json`

```json
{
  "controllers": {
    "X": { "port": "COM5", "baud": 115200, "serialnum": "025550131" },
    "Y": { "port": "COM3", "baud": 115200, "serialnum": "025550143" },
    "Z": { "port": "COM4", "baud": 115200, "serialnum": "025550149" }
  },
  "travel_ranges": {
    "X": { "min": 5.0, "max": 200.0 },
    "Y": { "min": 0.0, "max": 200.0 },
    "Z": { "min": 15.0, "max": 200.0 }
  },
  "motion": {
    "default_velocity": 10.0,
    "max_velocity": 20.0,
    "park_position": 200.0
  }
}
```

### Spot Detection Tuning — `device_drivers/spot_analysis/config.py`

All detection and inspection thresholds are in this file.  Edit constants here; no algorithm code changes needed.

### Camera DLL Path — `main.py`

```python
TL_DLL_DIR = r"C:\Program Files\Thorlabs\ThorImageCAM\Bin"
```

Change if the Thorlabs SDK is installed in a non-default location.
