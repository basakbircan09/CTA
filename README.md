# CTA – Computational Testing Apparatus

A laboratory automation desktop application for controlling a 3-axis PI motion stage, capturing images with a Thorlabs camera, detecting electrochemical plates, and analysing working-electrode spots for defects (bubbles, holes, non-uniformity).

---

## Table of Contents

1. [Overview](#overview)
2. [Project Structure](#project-structure)
3. [Hardware Requirements](#hardware-requirements)
4. [Software Requirements & Dependencies](#software-requirements--dependencies)
5. [How to Run](#how-to-run)
6. [Application UI Layout](#application-ui-layout)
7. [Button-by-Button Walkthrough](#button-by-button-walkthrough)
   - [Connect](#1-connect)
   - [Initialize](#2-initialize)
   - [Camera](#3-camera-startlive)
   - [Capture](#4-capture)
   - [Plate Detect](#5-plate-detect)
   - [Auto Adjust](#6-auto-adjust)
   - [WE Detect](#7-we-detect)
8. [Camera Settings Panel](#camera-settings-panel)
9. [Stage Control Panel](#stage-control-panel)
10. [Full File Reference](#full-file-reference)
    - [main.py](#mainpy)
    - [device_drivers/GPT_Merge.py](#device_driversgpt_mergepy)
    - [device_drivers/spot_analysis/](#device_driversspot_analysis)
    - [device_drivers/thorlabs_camera_wrapper.py](#device_driversthorldabs_camera_wrapperpy)
    - [device_drivers/plate_finder.py](#device_driversplate_finderpy)
    - [device_drivers/plate_auto_adjuster.py](#device_driversplate_auto_adjusterpy)
    - [device_drivers/PI_Control_System/](#device_driverspi_control_system)
11. [Output Artifacts](#output-artifacts)
12. [Configuration](#configuration)

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

## Project Structure

```
CTA/
├── main.py                                  # Application entry point – all GUI logic
├── requirements.txt                         # Python dependencies
│
├── device_drivers/
│   ├── GPT_Merge.py                         # Plate detection + spot detection (combined)
│   ├── plate_finder.py                      # Gray-plate-on-red-background detector
│   ├── plate_auto_adjuster.py               # Feedback loop: capture → detect → move stage
│   ├── thorlabs_camera_wrapper.py           # Thorlabs camera connect/capture/settings
│   ├── we_detection.py                      # Legacy spot/bubble detector (not used in main UI)
│   │
│   ├── spot_analysis/                       # Modular spot analysis pipeline (used by WE Detect)
│   │   ├── __init__.py
│   │   ├── config.py                        # Tuning constants for detection & inspection
│   │   ├── detection.py                     # Spot detection algorithm
│   │   ├── inspection.py                    # Per-spot defect inspection
│   │   ├── visualization.py                 # Draw contour overlays on images
│   │   ├── excel_export.py                  # Export results to .xlsx
│   │   └── pipeline.py                      # Orchestrates the full analysis end-to-end
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
│           └── main_window.py               # Legacy standalone PI GUI (not used in CTA main app)
│
├── artifacts/                               # All output images and Excel files go here
│   ├── captures/                            # Raw captured images from camera
│   ├── plate_detection/                     # Cropped plate images from Plate Detect
│   ├── we_detection/                        # Overlay images + spot_results.xlsx from WE Detect
│   └── auto_adjust/                         # Per-iteration images from Auto Adjust loop
│
└── config/                                  # (App-level config folder, reserved for future use)
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
pipython       # PI GCS2 controller communication
pylablib       # Thorlabs TL camera SDK wrapper
opencv-python  # Image processing (cv2)
numpy          # Numerical operations
openpyxl       # Excel export (.xlsx)
```

Install with:

```bash
pip install -r requirements.txt
```

The Thorlabs TL camera SDK DLLs (`thorlabs_tsi_camera_sdk`, `thorlabs_unified_sdk`) must also be installed on the system. The PI GCS2 DLL files (`PI_GCS2_DLL.dll`, `E816_DLL.dll`) must be present in the project root directory.

---

## How to Run

```bash
python main.py
```

The application starts with `use_mock=False`, meaning it expects real PI controllers and a real Thorlabs camera to be connected. If the hardware is absent the app still launches — camera absence is handled gracefully via file-picker fallback, and stage errors are shown in message boxes.

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
**Handler:** `SimpleStageApp.on_connect_clicked()` — `main.py:449`

**What it does:**

Establishes serial USB connections to all three PI motion controllers (X, Y, Z).

**Execution flow:**

1. Sets the status indicator to yellow `CONNECTING...`
2. Calls `self.connection_service.connect()` — this is an **async** call that returns a `Future`.
3. Blocks (`.result(timeout=30)`) until the connection future resolves or 30 seconds elapse.
4. On success: status turns `CONNECTED`.
5. On failure: status turns `ERROR`, a critical message box is shown.

**Files involved:**

| File | Role |
|---|---|
| `main.py` | Button handler, status update, error dialog |
| `device_drivers/PI_Control_System/services/connection_service.py` | `connect()` — dispatches connection to thread executor |
| `device_drivers/PI_Control_System/hardware/pi_manager.py` | `PIControllerManager` — iterates over all 3 axis controllers |
| `device_drivers/PI_Control_System/hardware/pi_controller.py` | `PIAxisController.connect()` — calls pipython `GCSDevice` open over COM port |
| `device_drivers/PI_Control_System/config/defaults.json` | COM ports, baud rates, serial numbers for each axis |
| `device_drivers/PI_Control_System/core/models.py` | `ConnectionState` enum used to track state |
| `device_drivers/PI_Control_System/services/event_bus.py` | Publishes `CONNECTION_STARTED`, `CONNECTION_SUCCEEDED` events |

---

### 2. Initialize

**Button:** `Initialize`
**Handler:** `SimpleStageApp.on_initialize_clicked()` — `main.py:464`

**What it does:**

References (homes) all three axes of the stage so the controller knows the absolute position, then moves the stage to the park position (200, 200, 200 mm).

**Execution flow:**

1. Checks `connection_service.state.connection` is `CONNECTED`; shows a warning if not.
2. Sets status to `INITIALIZING...`
3. Calls `self.connection_service.initialize()` — returns a `Future`; blocks for up to 120 seconds (referencing takes time as the stage moves to its limit switch).
4. Sets status to `PARKING...`
5. Calls `self.motion_service.move_to_position_safe_z(park_position)` where `park_position = Position(200.0, 200.0, 200.0)`.
   - Safe-Z move: Z is moved first if moving to a higher Z, or last if moving to a lower Z — to avoid mechanical collisions.
6. On success: status turns `READY`.

**Referencing order** (from `defaults.json`): Z → X → Y

**Files involved:**

| File | Role |
|---|---|
| `main.py` | Button handler, park position definition, status updates |
| `device_drivers/PI_Control_System/services/connection_service.py` | `initialize()` — references each axis using FPL mode |
| `device_drivers/PI_Control_System/hardware/pi_controller.py` | `reference()` — sends GCS `FPL` command to physical controller |
| `device_drivers/PI_Control_System/services/motion_service.py` | `move_to_position_safe_z()` — ordered Z-safe absolute move |
| `device_drivers/PI_Control_System/core/models.py` | `Position` dataclass (x, y, z floats) |
| `device_drivers/PI_Control_System/config/defaults.json` | `park_position: 200.0`, `reference_order: ["Z","X","Y"]` |

---

### 3. Camera (Start / Live)

**Button:** `Camera`
**Handler:** `SimpleStageApp.on_cam_start_clicked()` — `main.py:493`

**What it does:**

Toggles a live camera preview running at ~10 frames per second. The image display area updates continuously with the raw frame from the Thorlabs camera.

**Execution flow (Start):**

1. If `live_running` is False:
   - If camera is not connected, calls `self.camera.connect()`.
   - Starts `self.live_timer` (interval = 100 ms → ~10 fps).
   - `live_running = True`, button label changes to `Camera Stop (live)`.
2. Every 100 ms, `_update_live_view()` fires:
   - Calls `self.camera.grab_frame()` → returns a BGR `numpy.ndarray`.
   - Converts to `QPixmap` via `cv_to_qpixmap()` and sets it on the image label.

**Execution flow (Stop):**

1. Stops the timer.
2. `live_running = False`, button label reverts.

**Files involved:**

| File | Role |
|---|---|
| `main.py` | Toggle logic, QTimer setup, `_update_live_view()` callback |
| `device_drivers/thorlabs_camera_wrapper.py` | `ThorlabsCamera.connect()`, `grab_frame()` |

**`grab_frame()` detail** (`thorlabs_camera_wrapper.py:80`):

- Calls `self._cam.snap()` from pylablib to acquire one frame.
- If data is `uint16`: normalises each channel to 0–255 per-channel to avoid colour distortion.
- If data is 2D (grayscale): converts to BGR.
- Applies software white balance gains (`_apply_white_balance()`).
- Returns a BGR `uint8` `numpy.ndarray`.

---

### 4. Capture

**Button:** `Capture`
**Handler:** `SimpleStageApp.on_capture_clicked()` — `main.py:511`

**What it does:**

Takes a single still image. If the Thorlabs camera is available it captures from the camera and saves to disk. If the camera is not connected and cannot be connected, it opens a file picker so the user can load any existing image from disk. In both cases the image is stored as `self.last_image_path` for use by Plate Detect.

**Execution flow:**

1. Checks `self.camera.is_connected`.
2. If not connected: tries `self.camera.connect()`.
   - If `connect()` raises any exception → `camera_available = False`.
3. **Camera available path:**
   - Builds a filename from the current exposure, gain, and white-balance settings:
     `Photo_{exp}_{gain}_{R}_{G}_{B}.png`
   - Finds a unique filename (appends `_1`, `_2`, … if file already exists).
   - Calls `self.camera.save_frame(filename)` → captures and writes PNG to `artifacts/captures/`.
   - Stores path in `self.last_image_path`.
   - Displays the frame in the image panel.
4. **No camera path:**
   - Logs a warning: `Camera not connected. Please select an image file.`
   - Opens `QFileDialog.getOpenFileName` filtered to PNG/JPG/JPEG/BMP.
   - Reads the chosen file with `cv2.imread()`.
   - Stores path in `self.last_image_path`.
   - Displays the image in the image panel.

**Files involved:**

| File | Role |
|---|---|
| `main.py` | Full handler logic, file-picker fallback, filename construction |
| `device_drivers/thorlabs_camera_wrapper.py` | `connect()`, `save_frame()` (which calls `grab_frame()` then `cv2.imwrite`) |

**Output:** `artifacts/captures/Photo_<exp>_<gain>_<R>_<G>_<B>[_N].png`

---

### 5. Plate Detect

**Button:** `Plate Detect`
**Handler:** `SimpleStageApp.on_plate_clicked()` — `main.py:572`

**What it does:**

Detects the electrochemical plate in the current image and crops it out for further analysis. Uses the last captured image. If no image has been captured yet, asks the user to choose a file.

**Execution flow:**

1. Reads `self.last_image_path`.
2. If `None`, opens a file picker dialog.
3. Calls `analyze_plate_and_spots(image_path, save_dir)` from `GPT_Merge.py`.
4. Checks `result["error"]` and `result["plate_detected"]`; shows warning dialogs on failure.
5. Extracts `result["plate_image"]` (the cropped BGR image of the plate region).
6. Saves it as `artifacts/plate_detection/plate.png`.
7. Stores path in `self.last_plate_path` for use by WE Detect.
8. Displays the cropped plate in the image panel.
9. Shows an information dialog with the bounding box coordinates.

**Files involved:**

| File | Role |
|---|---|
| `main.py` | Handler, file-picker fallback, display, path storage |
| `device_drivers/GPT_Merge.py` | `analyze_plate_and_spots()` — full plate + spot pipeline |

**`analyze_plate_and_spots()` detail** (`GPT_Merge.py:187`):

1. `cv2.imread(image_path)` — loads image.
2. `resize_image(img, resize_percent)` — resizes (default 100% = full resolution).
3. `detect_plate(img)` — finds the plate bounding box:
   - Converts to grayscale.
   - `cv2.GaussianBlur` (3×3) then `cv2.Canny` edge detection (45, 40).
   - `cv2.dilate` edges with a 3×3 kernel.
   - `cv2.findContours` external contours.
   - Takes the **largest contour by area** and returns its `boundingRect`.
4. Crops `plate = img[py:py+ph, px:px+pw]`.
5. `detect_spots(plate)` — finds circular working electrode spots on the plate:
   - Grayscale → GaussianBlur (5×5).
   - `cv2.adaptiveThreshold` (Gaussian, blockSize=49, C=3, THRESH_BINARY_INV).
   - `cv2.morphologyEx` MORPH_OPEN with 3×3 kernel.
   - `cv2.findContours` external contours.
   - Filters by area (100–15,000 px²) and circularity (≥ 0.2).
   - Returns list of dicts: `{contour, center, radius}`.
6. `sort_and_label(spots)` — sorts spots into rows (by Y), then columns (by X) within each row, labels them A1, A2, B1, B2, …
7. `compute_inspection_radius(spots)` — `r_check = 3 × (smallest_radius / 4)`.
8. For each spot, `has_bubble_or_hole(gray_plate, spot, r_check)`:
   - Circular mask around spot center.
   - **Bubble check:** coefficient of variation `CV = std / mean`; if CV > 0.3 → bubble.
   - **Hole check:** Otsu threshold on masked region, `cv2.findContours` with RETR_CCOMP; if any contour has a parent (hierarchy[3] ≠ -1) → hole detected.
   - Returns `True` if either condition met.
9. Splits spots into `accepted` and `rejected`.
10. `draw_results()` draws contours, center dots, and labels on the image.
11. Saves `all_detected.png` and `accepted_only.png` to `save_dir`.
12. Returns a dict with `plate_detected`, `plate_bbox`, `plate_image`, `all_spots`, `accepted_spots`, `rejected_spots`, `all_spots_image`, `accepted_spots_image`, `error`.

**Output:** `artifacts/plate_detection/plate.png`

---

### 6. Auto Adjust

**Button:** `Auto Adjust`
**Handler:** `SimpleStageApp.on_adjust_clicked()` — `main.py:599`

**What it does:**

Runs a closed-loop feedback loop to automatically centre the plate within the camera frame. It repeatedly captures an image, analyses whether the plate is fully visible, and moves the stage in the appropriate direction until success or the iteration limit is reached.

**Execution flow:**

1. Checks `_is_stage_ready()` — aborts with a warning if the stage is not connected + initialized.
2. Connects camera if not already connected.
3. Calls `auto_adjust_plate(motion_service, camera, save_dir, step_mm=5.0, max_iterations=10)`.
4. Logs all step messages from the returned `steps_log`.
5. Shows success/failure message box.

**`auto_adjust_plate()` detail** (`plate_auto_adjuster.py:14`):

For each iteration (up to 10):

1. `camera.save_frame(img_path)` — captures frame to `artifacts/auto_adjust/auto_adjust_{i}.png`.
2. `gray_plate_on_red(img_path, margin_frac=0.02)` — detects gray plate on red background:
   - Converts image to HSV.
   - Builds two HSV masks for red (hue 0–10° and 170–180°) and combines with bitwise OR.
   - Morphological close (5×5 kernel, 2 iterations) to fill gaps.
   - Finds largest red contour → `red_bbox (rx, ry, rw, rh)`.
   - Inverts red mask to isolate non-red regions.
   - Thresholds grayscale (< 150) to find dark areas (the plate).
   - Finds contours, filters by area (≥ 2000 px²) and 4-corner polygon (`approxPolyDP`).
   - Picks the largest valid quadrilateral → `plate_bbox`.
   - Checks if plate bbox fits inside red bbox with a 2% margin on each side.
   - If not centred, computes direction hint: `"left"`, `"right"`, `"up"`, `"down"`, or combined (e.g., `"left_up"`).
   - Returns `{fully_in_frame, move_hint, rect_bbox, output_image, ...}`.
3. If `fully_in_frame = True` → returns success immediately.
4. Maps `move_hint` to stage moves:
   - `"left"` → `move_axis_relative(X, +step_mm)`
   - `"right"` → `move_axis_relative(X, -step_mm)`
   - `"up"` → `move_axis_relative(Y, +step_mm)`
   - `"down"` → `move_axis_relative(Y, -step_mm)`
   - Unknown hint → stops loop and returns failure.
5. Waits for both X and Y futures to complete before the next iteration.

**Files involved:**

| File | Role |
|---|---|
| `main.py` | Handler, stage-ready check, result logging |
| `device_drivers/plate_auto_adjuster.py` | `auto_adjust_plate()` — the feedback loop |
| `device_drivers/plate_finder.py` | `gray_plate_on_red()` — HSV-based plate visibility check |
| `device_drivers/thorlabs_camera_wrapper.py` | `save_frame()` — capture image per iteration |
| `device_drivers/PI_Control_System/services/motion_service.py` | `move_axis_relative()` — async X/Y stage moves |
| `device_drivers/PI_Control_System/core/models.py` | `Axis.X`, `Axis.Y` enums |

**Output:** `artifacts/auto_adjust/auto_adjust_1.png` … `auto_adjust_N.png` (one per iteration), plus `*_checked.png` annotated copies saved alongside each.

---

### 7. WE Detect

**Button:** `WE Detect`
**Handler:** `SimpleStageApp.on_we_clicked()` — `main.py:637`

**What it does:**

Runs the full spot analysis pipeline from `device_drivers/spot_analysis/` on the detected plate image. Every spot is inspected for defects (non-uniformity, bubbles). Results are colour-coded on an overlay image (blue = good, red = bad) and exported to an Excel file.

**Execution flow:**

1. Reads `self.last_plate_path` (set by Plate Detect).
2. If `None`, prompts the user with a Yes/No dialog asking whether to select an image manually.
   - Yes → `QFileDialog` to pick a PNG/JPG/BMP.
   - No → returns.
3. Calls `run_spot_analysis(image_path, str(save_dir), export_excel=True)` from `spot_analysis/pipeline.py`.
4. Retrieves `result["overlay_image"]` and displays it on the image panel.
5. Reads `accepted_spots`, `rejected_spots`, `all_spots` counts.
6. Collects labels of rejected spots (e.g., `["A2", "B3"]`).
7. Logs the summary and shows an information or warning message box depending on whether any spots are rejected.

**`run_spot_analysis()` detail** (`spot_analysis/pipeline.py:12`):

1. `cv2.imread(image_path)` — loads the plate image.
2. `detect_spots(img)` (`spot_analysis/detection.py`):
   - `preprocess_for_detection(img)`:
     - Convert BGR → grayscale.
     - Large GaussianBlur (kernel = 81×81) to estimate the illumination background.
     - `cv2.divide(gray, background, scale=255)` — normalises away uneven lighting.
     - CLAHE (Contrast Limited Adaptive Histogram Equalisation, clipLimit=2.0, tileSize=8×8) — sharpens local contrast.
   - GaussianBlur (5×5) on normalised image.
   - `cv2.adaptiveThreshold` (Gaussian, blockSize=35, C=2, THRESH_BINARY_INV) — binarises.
   - `cv2.morphologyEx` MORPH_OPEN (2×2 kernel) — removes small noise.
   - `cv2.morphologyEx` MORPH_CLOSE (3×3 kernel) — fills small gaps.
   - `cv2.findContours` external only.
   - For each contour: compute `area`, `circularity = 4πA/P²`, `solidity = area / convexHullArea`.
   - **Accept** if: area ∈ [450, 15,000] px², circularity ≥ 0.45, solidity ≥ 0.65.
   - **Reject candidate** (not a spot) otherwise, with a `reason` field (`"area"`, `"circularity"`, or `"solidity"`).
   - Returns `spots` list, `rejected_candidates` list, and `debug` dict of intermediate images.
3. For each accepted spot, `inspect_spot_defects(gray_norm, spot)` (`spot_analysis/inspection.py`):
   - Draws a filled contour mask on a blank image.
   - Extracts pixel values from `gray_norm` under the mask.
   - If fewer than 80 pixels → returns `(False, {warning: "too_few_pixels"})`.
   - Computes **median** and **MAD** (Median Absolute Deviation) of pixel intensities.
   - Modified Z-scores: `z = |val − median| / (1.4826 × MAD)`.
   - `outlier_frac = fraction of pixels with z > 4.5`.
   - If `outlier_frac > 0.16` → appends `"nonuniform"` to reasons list → spot is `is_bad = True`.
   - Returns `(is_bad, metrics_dict)`.
4. Splits spots into `accepted` and `rejected` lists.
5. `draw_accept_reject_overlay(img, spots)` (`spot_analysis/visualization.py`):
   - For each spot: draws its contour in **red** if `is_bad`, **blue** if good.
   - Draws a small dot at the centroid.
   - Writes the spot label (e.g., `"A1"`) next to the centroid if present.
6. If `output_dir` is provided:
   - Saves `overlay.png` to the output directory.
   - `export_results_to_excel(path, result)` (`spot_analysis/excel_export.py`):
     - Creates an `.xlsx` workbook with two sheets:
       - **Summary**: Total detected / Accepted / Rejected counts.
       - **Spots**: Per-spot table with Label, Status, Area, Circularity, Solidity.
7. Returns `{all_spots, accepted_spots, rejected_spots, rejected_candidates, overlay_image}`.

**Files involved:**

| File | Role |
|---|---|
| `main.py` | Handler, image display, summary logging, message box |
| `device_drivers/spot_analysis/pipeline.py` | `run_spot_analysis()` — orchestrates steps 1–7 |
| `device_drivers/spot_analysis/detection.py` | `detect_spots()`, `preprocess_for_detection()` |
| `device_drivers/spot_analysis/inspection.py` | `inspect_spot_defects()` — MAD-based outlier test |
| `device_drivers/spot_analysis/visualization.py` | `draw_accept_reject_overlay()` — colour-coded contour drawing |
| `device_drivers/spot_analysis/excel_export.py` | `export_results_to_excel()` — writes `.xlsx` |
| `device_drivers/spot_analysis/config.py` | All tuning constants (area range, circularity, MAD thresholds, etc.) |

**Output:**
- `artifacts/we_detection/overlay.png` — colour-coded spot image
- `artifacts/we_detection/spot_results.xlsx` — Excel report

---

## Camera Settings Panel

All controls are in `main.py` — the camera settings group.

### Exposure

- **Spinbox:** `spin_exposure` — range 1.0–5,000.0 ms, default 100 ms.
- **Set button handler:** `on_set_exposure()` (`main.py:716`).
  - Reads `spin_exposure.value()`, divides by 1000 to convert ms → seconds.
  - Calls `self.camera.set_exposure(exposure_sec)`.
  - In `thorlabs_camera_wrapper.py`: forwards to `self._cam.set_exposure(exposure_sec)` (pylablib API).

### Gain

- **Spinbox:** `spin_gain` — range 0.0–48.0 dB, default 0.
- **Set button handler:** `on_set_gain()` (`main.py:729`).
  - Calls `self.camera.set_gain(gain)`.
  - In `thorlabs_camera_wrapper.py`: calls `self._cam.set_gain(gain)` if the camera object supports it.

### White Balance

- **Preset dropdown:** `combo_wb` — Default, Warm, Cool, Reduce NIR, Custom.
- **Handler:** `on_wb_preset_changed(preset)` (`main.py:741`):
  - Maps preset name to `(R, G, B)` gain tuples.
  - Updates `spin_wb_r`, `spin_wb_g`, `spin_wb_b` and immediately calls `on_apply_white_balance()`.

| Preset | R | G | B |
|---|---|---|---|
| Default | 1.0 | 1.0 | 1.0 |
| Warm | 1.0 | 0.9 | 0.7 |
| Cool | 0.9 | 1.0 | 1.2 |
| Reduce NIR | 0.6 | 0.8 | 1.0 |
| Custom | (unchanged) | | |

- **Apply button handler:** `on_apply_white_balance()` (`main.py:757`):
  - Calls `self.camera.set_white_balance(r, g, b)`.
  - In `thorlabs_camera_wrapper.py`: clamps each gain to [0.1, 4.0] and stores in `self._white_balance`.
  - Applied during `grab_frame()` via `_apply_white_balance()`:
    - Converts frame to `float32`.
    - Multiplies each BGR channel by the corresponding gain (B channel ← blue gain, G ← green, R ← red).
    - Clips to [0, 255] and converts back to `uint8`.

**Files involved:** `main.py`, `device_drivers/thorlabs_camera_wrapper.py`

---

## Stage Control Panel

All controls are in `main.py` — the stage control group.

### Position Display

- `pos_label` — monospace label showing `X=?.?? Y=?.?? Z=?.??`
- **Refresh button handler:** `on_refresh_position()` (`main.py:774`):
  - Calls `motion_service.get_current_position()` → returns `Position(x, y, z)`.
  - Updates label and also pre-fills the "Go to" spinboxes with current position.

### Jog (Relative Move)

- Buttons: `±X`, `±Y`, `±Z` (six buttons total).
- **Handler:** `on_jog_axis(axis, direction)` (`main.py:790`):
  - `step = spin_step.value() * direction` (direction is +1 or −1).
  - Calls `motion_service.move_axis_relative(axis, step)` → returns a `Future`.
  - Blocks `.result(timeout=30)`.
  - Calls `on_refresh_position()` after move completes.

### Absolute Move (Go To)

- Three spinboxes: `spin_goto_x`, `spin_goto_y`, `spin_goto_z` — range 0–300 mm.
- **Go button handler:** `on_goto_position()` (`main.py:805`):
  - Builds `Position(x, y, z)` from spinbox values.
  - Calls `motion_service.move_to_position_safe_z(target)`.
  - Safe-Z logic in `motion_service.py`:
    - Moving to higher Z → move Z first (lift before moving XY).
    - Moving to lower Z → move XY first (position before lowering).
  - Blocks `.result(timeout=60)`.
  - Refreshes position display.

**Files involved:**

| File | Role |
|---|---|
| `main.py` | All panel UI and handlers |
| `device_drivers/PI_Control_System/services/motion_service.py` | `move_axis_relative()`, `move_to_position_safe_z()`, `get_current_position()` |
| `device_drivers/PI_Control_System/hardware/pi_controller.py` | Low-level GCS move commands |
| `device_drivers/PI_Control_System/core/models.py` | `Axis` enum, `Position` dataclass |

---

## Full File Reference

### `main.py`

The single file that defines the entire GUI application (`SimpleStageApp(QMainWindow)`).

| Method | Line | Description |
|---|---|---|
| `__init__` | 34 | Constructs all UI widgets, connects signals to handlers, initialises hardware objects |
| `log()` | 395 | Appends timestamped `[INFO]`/`[WARN]`/`[ERROR]` message to the log text box |
| `set_status()` | 405 | Updates the coloured status indicator (red/yellow/green) |
| `cv_to_qpixmap()` | 433 | Converts a BGR `numpy.ndarray` to a scaled `QPixmap` for the image label |
| `on_connect_clicked()` | 449 | Connects PI stage controllers |
| `on_initialize_clicked()` | 464 | References axes and parks stage |
| `on_cam_start_clicked()` | 493 | Toggles live camera view |
| `on_capture_clicked()` | 511 | Captures from camera or opens file picker if no camera |
| `on_plate_clicked()` | 572 | Runs plate detection via `GPT_Merge` |
| `on_adjust_clicked()` | 599 | Runs auto-adjust feedback loop |
| `on_we_clicked()` | 637 | Runs WE spot analysis via `spot_analysis` pipeline |
| `on_set_exposure()` | 716 | Applies exposure spinbox value to camera |
| `on_set_gain()` | 729 | Applies gain spinbox value to camera |
| `on_wb_preset_changed()` | 741 | Updates RGB spinboxes on preset selection |
| `on_apply_white_balance()` | 757 | Applies RGB white balance gains to camera |
| `_is_stage_ready()` | 770 | Returns True if stage is connected + initialized |
| `on_refresh_position()` | 774 | Reads and displays current XYZ stage position |
| `on_jog_axis()` | 790 | Moves one axis by step size |
| `on_goto_position()` | 805 | Moves stage to absolute XYZ coordinates |
| `_update_live_view()` | 827 | Timer callback for live preview frames |
| `closeEvent()` | 838 | Clean disconnect of camera and stage on app exit |

---

### `device_drivers/GPT_Merge.py`

Unified plate + spot detection used by the **Plate Detect** button.

| Function | Description |
|---|---|
| `resize_image(img, percent)` | Resize image by percentage using Lanczos interpolation |
| `detect_plate(image)` | Canny edge → largest contour → bounding rect |
| `detect_spots(plate_img, ...)` | Adaptive threshold → filter by area + circularity → spot list |
| `compute_inspection_radius(spots)` | `r_check = 3 × (min_radius / 4)` |
| `has_bubble_or_hole(gray, spot, r_check)` | CV-based bubble check + Otsu topology hole check |
| `sort_and_label(spots)` | Sort into rows/columns, assign grid labels (A1, B2, …) |
| `draw_results(image, spots, px, py)` | Draw contours, centers, and labels on image |
| `analyze_plate_and_spots(image_path, ...)` | **Main entry point** — full pipeline, returns result dict |

**Tuning parameters (top of file):**

| Constant | Value | Meaning |
|---|---|---|
| `DEFAULT_MIN_SPOT_AREA` | 100 px² | Smallest valid spot |
| `DEFAULT_MAX_SPOT_AREA` | 15,000 px² | Largest valid spot |
| `DEFAULT_MIN_CIRCULARITY` | 0.2 | Minimum roundness (0=line, 1=circle) |
| `DEFAULT_MAX_INTENSITY_CV` | 0.3 | Max coefficient of variation for bubble detection |
| `DEFAULT_RESIZE_PERCENT` | 100 | No resize (full resolution) |

---

### `device_drivers/spot_analysis/`

Modular pipeline used by the **WE Detect** button. More rigorous than `GPT_Merge`.

#### `config.py`

All detection and inspection tuning constants. Edit these to tune sensitivity without touching algorithm code.

| Constant | Value | Purpose |
|---|---|---|
| `DEFAULT_MIN_SPOT_AREA` | 450 px² | Minimum valid spot area |
| `DEFAULT_MAX_SPOT_AREA` | 15,000 px² | Maximum valid spot area |
| `DEFAULT_MIN_CIRCULARITY` | 0.45 | Minimum circularity (stricter than GPT_Merge) |
| `DEFAULT_MIN_SOLIDITY` | 0.65 | Minimum solidity (area / convex hull area) |
| `DEFAULT_BG_BLUR_K` | 81 | Kernel size for background estimation blur |
| `DEFAULT_CLAHE_CLIP` | 2.0 | CLAHE clip limit |
| `DEFAULT_CLAHE_TILE` | (8, 8) | CLAHE tile grid size |
| `DEFAULT_THRESH_BLOCKSIZE` | 35 | Adaptive threshold block size |
| `DEFAULT_THRESH_C` | 2 | Adaptive threshold constant C |
| `DEFAULT_OPEN_KERNEL` | 2 | Morphological open kernel size |
| `DEFAULT_CLOSE_KERNEL` | 3 | Morphological close kernel size |
| `DEFAULT_MAD_K` | 4.5 | Z-score multiplier for outlier detection |
| `DEFAULT_MAX_OUTLIER_FRAC` | 0.16 | Max fraction of outlier pixels before spot is bad |
| `DEFAULT_DARK_Q` | 10 | 10th percentile intensity (dark tone reference) |
| `DEFAULT_BRIGHT_Q` | 95 | 95th percentile intensity (bright tone reference) |

#### `detection.py`

| Function | Description |
|---|---|
| `preprocess_for_detection(bgr)` | Grayscale → background subtraction → CLAHE → returns normalised grayscale |
| `detect_spots(image)` | Full detection: preprocess → blur → adaptive threshold → morphology → filter contours |

#### `inspection.py`

| Function | Description |
|---|---|
| `inspect_spot_defects(gray, spot)` | Mask spot, extract pixel values, compute MAD Z-scores, flag if outlier fraction exceeds threshold |

#### `visualization.py`

| Function | Description |
|---|---|
| `draw_accept_reject_overlay(image, spots)` | Draw red (bad) or blue (good) contours, center dots, and labels |

#### `excel_export.py`

| Function | Description |
|---|---|
| `export_results_to_excel(path, result)` | Write Summary sheet (counts) + Spots sheet (per-spot metrics) to `.xlsx` |

#### `pipeline.py`

| Function | Description |
|---|---|
| `run_spot_analysis(image_path, output_dir, export_excel)` | Full pipeline: load → detect → inspect → visualise → save overlay + Excel → return result dict |

---

### `device_drivers/thorlabs_camera_wrapper.py`

Thin wrapper around `pylablib.devices.Thorlabs.ThorlabsTLCamera`.

| Method | Description |
|---|---|
| `connect()` | Sets DLL path, calls `list_cameras_tlcam()`, opens first camera, sets 100 ms exposure and 0 gain |
| `disconnect()` | Stops acquisition, closes camera object |
| `grab_frame()` | `snap()` → normalise dtype → handle grayscale/colour → apply white balance → return BGR `ndarray` |
| `save_frame(path)` | `grab_frame()` then `cv2.imwrite(path, frame)` |
| `set_exposure(sec)` | Forwards to `self._cam.set_exposure()` |
| `set_gain(db)` | Forwards to `self._cam.set_gain()` |
| `set_white_balance(r, g, b)` | Stores gains clamped to [0.1, 4.0] |
| `_apply_white_balance(frame)` | Multiplies BGR channels by `[blue_gain, green_gain, red_gain]`, clips to [0,255] |

---

### `device_drivers/plate_finder.py`

| Function | Description |
|---|---|
| `gray_plate_on_red(image_path, margin_frac, debug)` | HSV red detection → dark non-red region → 4-point polygon filter → inside-red check → direction hint |

Returns:

| Key | Type | Description |
|---|---|---|
| `rect_bbox` | `(x,y,w,h)` or `None` | Plate bounding box in image |
| `fully_in_frame` | `bool` | Whether plate is inside red background with margin |
| `move_hint` | `str` | `"ok"`, `"left"`, `"right"`, `"up"`, `"down"`, `"left_up"`, `"no_red"`, `"no_plate"`, `"adjust"` |
| `output_image` | `ndarray` | Annotated image |
| `save_path` | `str` | Path to saved `*_checked.png` |

---

### `device_drivers/plate_auto_adjuster.py`

| Function | Description |
|---|---|
| `auto_adjust_plate(motion_service, camera, save_dir, step_mm, max_iterations)` | Feedback loop: capture → `gray_plate_on_red` → map hint to ΔX/ΔY → move stage → repeat |

Returns `(fully_in_frame: bool, final_hint: str, log_messages: List[str])`.

---

### `device_drivers/PI_Control_System/`

#### `app_factory.py`

| Function | Description |
|---|---|
| `create_services(use_mock)` | Loads config, creates `ThreadPoolExecutor`, `EventBus`, 3 axis controllers, `PIControllerManager`, `ConnectionService`, `MotionService` |

#### `config/defaults.json`

Hardware configuration file. Contains COM ports, baud rates, serial numbers, axis travel ranges, velocity limits, and park position. Loaded at startup by `config/loader.py`.

#### `core/models.py`

| Class | Description |
|---|---|
| `Axis` | Enum: `X`, `Y`, `Z` |
| `Position` | Dataclass with `x`, `y`, `z` floats (mm) |
| `ConnectionState` | Enum: `DISCONNECTED`, `CONNECTING`, `CONNECTED`, `ERROR` |
| `InitializationState` | Enum: `NOT_INITIALIZED`, `INITIALIZING`, `INITIALIZED` |
| `AxisConfig` | Per-axis config: port, baud, serial, travel range, velocity |
| `SystemState` | Snapshot of all state at a moment in time |

#### `hardware/pi_controller.py`

`PIAxisController` — wraps a `pipython.GCSDevice` for one physical controller.

| Method | Description |
|---|---|
| `connect()` | Opens GCS device over USB/serial |
| `reference()` | Sends FPL (Forward Position Limit) homing command |
| `move_absolute(position)` | GCS `MOV` command |
| `move_relative(distance)` | GCS `MVR` command |
| `get_position()` | GCS `qPOS` query |

#### `hardware/mock_controller.py`

`MockAxisController` — identical interface to `PIAxisController` but simulates motion in memory. Used when `use_mock=True`.

#### `services/connection_service.py`

Manages the full lifecycle of connecting and initialising all axes. All public methods return `Future` objects (non-blocking).

| Method | Description |
|---|---|
| `connect()` | Dispatches `_connect_all()` to thread executor |
| `initialize()` | Dispatches `_initialize_all()` to thread executor |
| `shutdown()` | Disconnects all controllers |
| `is_ready()` | Returns True if both `CONNECTED` and `INITIALIZED` |

#### `services/motion_service.py`

All motion commands are non-blocking (return `Future`).

| Method | Description |
|---|---|
| `move_to_position(target)` | Simultaneous XYZ move |
| `move_to_position_safe_z(target)` | Safe ordered move (Z first if going up, Z last if going down) |
| `move_axis_relative(axis, distance)` | Jog one axis by `distance` mm |
| `move_axis_absolute(axis, position)` | Move one axis to absolute `position` mm |
| `get_current_position()` | Returns current `Position` snapshot |

#### `services/event_bus.py`

Simple publish/subscribe system. Events published include `CONNECTION_STARTED`, `CONNECTION_SUCCEEDED`, `STATE_CHANGED`, `MOTION_STARTED`, `MOTION_COMPLETED`, `ERROR`.

---

## Output Artifacts

All output files are written under `artifacts/` in the project root. The folder is created automatically.

| Directory | Created by | Contents |
|---|---|---|
| `artifacts/captures/` | Capture button | `Photo_<exp>_<gain>_<R>_<G>_<B>.png` — raw captured frames |
| `artifacts/plate_detection/` | Plate Detect button | `plate.png` — cropped plate region; `all_detected.png`, `accepted_only.png` |
| `artifacts/we_detection/` | WE Detect button | `overlay.png` — colour-coded spot overlay; `spot_results.xlsx` — Excel report |
| `artifacts/auto_adjust/` | Auto Adjust button | `auto_adjust_1.png` … `auto_adjust_N.png` — frame captured per iteration; `*_checked.png` — annotated copies |

---

## Configuration

### PI Stage — `device_drivers/PI_Control_System/config/defaults.json`

Edit this file to change COM ports, serial numbers, travel limits, velocity, or park position. No code changes are needed.

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

Edit constants in this file to adjust detection sensitivity without touching algorithm logic.

### Camera DLL Path — `main.py` line 44

```python
TL_DLL_DIR = r"C:\Program Files\Thorlabs\ThorImageCAM\Bin"
```

Change this if the Thorlabs SDK is installed in a non-default location.
