# CTA Imaging Detection Methodology Report

## 1. System Overview

The CTA (Camera, Thorlabs & Automation) project is a Python 3.13 / PySide6 desktop application for automated electrochemical sample array inspection. It integrates:

- **Thorlabs CS165CU** scientific camera (via pylablib / ThorCam SDK)
- **PI (Physik Instrumente) XYZ translation stages** (3x C-863/Mercury controllers via pipython GCS protocol)
- **Computer vision pipeline** (OpenCV + scikit-image) for plate detection, spot detection, and defect classification

The system captures high-resolution images of electrode plates, automatically detects deposited spots (working electrodes), classifies them for defects (bubbles, holes, faint deposits), and labels them on a grid. It is designed as the vision-and-positioning subsystem for the GOED (General Orchestrator for Electrochemistry Devices) platform.

---

## 2. Hardware Integration Architecture

### 2.1 Camera Subsystem

**Driver:** `device_drivers/thorlabs_camera_wrapper.py`
**SDK:** pylablib (`pylablib.devices.Thorlabs.ThorlabsTLCamera`) wrapping the ThorCam DLL

| Feature | Implementation |
|---------|---------------|
| Connection | Auto-detect first available camera via `list_cameras_tlcam()` |
| Frame capture | Single-frame blocking: `cam.snap()` returns raw array |
| Bit depth | 16-bit sensor output normalized to 8-bit per-channel (`(pixel - min) / (max - min) * 255`) |
| Color handling | RGB (native) to BGR (OpenCV convention) conversion |
| White balance | Software-based: 5 presets (Default, Warm, Cool, Reduce NIR, Custom) with per-channel R/G/B gains (0.1-4.0) |
| Exposure | 1-5000 ms, set via `cam.set_exposure(seconds)` |
| Gain | 0-48 dB, set via `cam.set_gain(dB)` |
| Live view | QTimer at 100 ms interval (~10 fps), calls `grab_frame()` per tick |

**Photo naming convention:** Filenames encode all capture parameters for reproducibility:
```
Photo_{exposure:.1f}_{gain:.1f}_{R:.2f}_{G:.2f}_{B:.2f}.png
```

### 2.2 Stage Subsystem

**Driver:** `device_drivers/PI_Control_System/hardware/pi_controller.py`
**SDK:** pipython (`pipython.GCSDevice`) communicating over USB

Three independent PI controllers (one per axis), connected via serial number:

| Axis | Serial | COM | Travel Range | Default Velocity |
|------|--------|-----|-------------|-----------------|
| X | 025550131 | COM5 | 5-200 mm | 10 mm/s |
| Y | 025550143 | COM3 | 0-200 mm | 10 mm/s |
| Z | 025550149 | COM4 | 15-200 mm | 10 mm/s |

**Initialization sequence (per axis):**
1. `CST` -- configure stage model (62309260)
2. `SVO` -- enable servo mode
3. `FPL` -- reference move (find negative limit switch)
4. `MVR(-0.1)` -- back off 0.1 mm from limit
5. `VEL` -- set operating velocity

**Safety:** Reference order is Z -> X -> Y (Z retracts first to avoid collisions). The `move_to_position_safe_z()` method ensures Z moves up before XY, and XY complete before Z moves down.

### 2.3 Service Architecture

```
PIAxisController (per axis, wraps GCSDevice)
         |
PIControllerManager (coordinates 3 axes, Z-safety ordering)
         |
    +----+----+
    |         |
ConnectionService    MotionService
    |         |
    +----+----+
         |
      EventBus (thread-safe pub/sub)
         |
      GUI (SimpleStageApp)
```

All motion commands return `Future` objects from a shared `ThreadPoolExecutor(4)`. The `EventBus` publishes 15 event types for connection state transitions, enabling decoupled GUI updates.

---

## 3. Imaging Detection Pipeline

### 3.1 Plate Detection

**Function:** `detect_plate(image)` -- identical in v2 and v3

The plate is located within the full camera frame via edge detection:

```
Input BGR image
  -> Grayscale conversion
  -> GaussianBlur (11x11 kernel)
  -> Canny edge detection (low=30, high=90, 1:3 hysteresis)
  -> Morphological dilation (3x3, 2 iterations)
  -> Find contours (RETR_EXTERNAL)
  -> Select largest contour by area
  -> Return bounding rectangle (x, y, w, h)
```

The 11x11 blur suppresses fine-grained spot texture so Canny detects only the plate boundary edge. Two iterations of dilation connect gaps at corners for a complete contour.

**Alternative plate finder** (`plate_finder.py`) -- used only for auto-adjustment:
A color-based approach for detecting a gray plate on a known red background sheet using HSV color segmentation, producing directional movement hints (left/right/up/down).

### 3.2 Spot Detection Evolution

#### v1 -- Fixed Adaptive Threshold (`GPT_Merge.py`)

```
Plate ROI -> Grayscale -> GaussianBlur(5x5)
  -> adaptiveThreshold(GAUSSIAN_C, block_size=49, C=3)
  -> morphologyEx(MORPH_OPEN)
  -> findContours -> filter by area [300, 15000] and circularity >= 0.4
```

**Limitations:** All parameters hardcoded. Works only for a specific camera resolution and illumination level. Changing zoom, camera model, or lighting causes systematic miss-detections.

#### v2 -- Self-Calibrating Adaptive Parameters (`GPT_Merge_v2.py`)

Key innovations over v1:

1. **CLAHE preprocessing** (`clipLimit=2.0, tileGridSize=(8,8)`): Contrast Limited Adaptive Histogram Equalization normalizes non-uniform illumination. Each 8x8 tile gets independent histogram equalization, making spots at different plate positions appear with consistent contrast.

2. **Adaptive block_size and C:**
   ```
   block_size = clamp(plate_short_side / 4, 21, 251), forced odd
   C = clamp(round(std(gray_blur) * 0.22), 4, 16)
   ```
   - `block_size` scales with plate pixel dimensions
   - `C` (brightness subtraction) scales with local contrast energy

3. **Resolution-independent area bounds:**
   ```
   scale = (short_side / 500)^2
   scaled_min = max(base_min * scale, 50)
   scaled_max = max(base_max * scale, scaled_min * 10)
   ```

4. **Per-spot inspection radius:** `max(spot.radius * 0.75, 5.0)` instead of global minimum radius

5. **Corrected Otsu:** Computed on masked pixel values only, not zero-padded image

#### v3 -- Ensemble Detection (`GPT_Merge_v3.py`)

Replaces the single adaptive-threshold detector with a two-detector ensemble:

**Detector 1: OpenCV SimpleBlobDetector**
```
Threshold sweep: 10 -> 220, step 5 (~42 levels)
Filters: dark blobs (blobColor=0), area [eff_min, eff_max],
         circularity >= 0.25, convexity >= 0.3, inertia >= 0.15
```
Handles illumination gradients natively by testing multiple threshold levels and merging nearby detections across levels.

**Detector 2: scikit-image Determinant of Hessian (DoH)**
```
Sigma range: derived from area bounds, capped at short_side/25
Scales: 15 sigma levels, threshold = 0.008
```
Computes second-order derivatives (Hessian matrix) at multiple scales. Detects both dark-on-light AND light-on-dark blobs (polarity-agnostic). Complementary to SimpleBlobDetector's threshold-sweep approach.

**Ensemble merge:**
Union of both detector results with proximity-based deduplication. For overlapping detections (center distance < plate_short_side/40), the detection with larger area is kept.

**Border exclusion:** Spots within 4% of plate edges are removed (edge regions prone to lighting artifacts).

**Contour refinement:** Since both detectors return only center+radius (not actual contours), a refinement step extracts real spot boundaries:
```
For each detected blob:
  1. Define local ROI (1.5x radius around center)
  2. Local Otsu threshold within ROI
  3. Morphological cleanup (open + close)
  4. Find contours, select nearest to expected center
  5. Replace synthetic circle with real contour
  6. Recompute area, circularity from real boundary
```

**Post-refinement minimum area filter:** Drops spots whose refined contour area fell below 50% of the adaptive minimum.

### 3.3 Defect Classification

Three independent rejection checks (v3), applied in order:

#### Check 1: Faint Spot Detection (v3 only)

```
inner_mask = circle at spot center with radius r
ring_mask = annulus from r to 2r (local background)
contrast = (mean_background - mean_spot) / mean_background
REJECT if contrast < 0.08 (spot not 8% darker than surroundings)
```

A real deposit absorbs more light and should be noticeably darker than the surrounding plate. Faint detections are typically noise artifacts or failed deposits.

#### Check 2: Bubble Detection (CV threshold)

```
values = grayscale pixels inside circular inspection region (75% of spot radius)
cv_val = std(values) / (mean(values) + 1e-6)
REJECT if cv_val > 0.70
```

The Coefficient of Variation measures intensity non-uniformity. Bubbles trapped in the deposit create bright inclusions that raise variance dramatically. A healthy uniform deposit has low CV.

#### Check 3: Hole Detection (topology)

```
Otsu threshold computed from ROI pixel values only (not zero-padded)
Applied to grayscale plate, masked to inspection region
findContours with RETR_CCOMP (2-level hierarchy)
REJECT if any inner contour (has parent) > 10% of spot area
```

`RETR_CCOMP` retrieves contour topology. Inner contours (those with a parent contour) indicate voids/holes in the deposit. The 10% area threshold prevents micro-speckles from triggering false detections.

### 3.4 Spot Labeling

Spots are sorted into rows by Y-coordinate clustering, then labeled on a grid:

```
row_thresh = max(percentile_75(y_diffs) * 1.2, 15px)
For each spot: assign to existing row if |y - row_mean_y| < threshold
              else create new row
Sort each row by X (left to right)
Label: chr(65 + row) + str(col + 1)  -->  A1, A2, B1, B2, ...
```

Using the running mean of Y-coordinates per row (not a fixed anchor) provides stable clustering.

### 3.5 Result Visualization

Three output images are generated:

| Output | Colors | Purpose |
|--------|--------|---------|
| `all_detected.png` | All spots in green | Shows everything the pipeline found |
| `accepted_only.png` | Accepted spots in blue | Shows only non-defective deposits |
| `combined.png` | Green=accepted, Red=rejected | Quick visual comparison of selection |

Each spot is drawn with its real contour outline, a red centroid dot, and its grid label (e.g., "A1").

---

## 4. End-to-End Workflow (CTA + GOED Integration)

The CTA system operates as the vision-and-positioning subsystem within the GOED (General Orchestrator for Electrochemistry Devices) platform. The complete workflow from sample placement to electrochemical measurement is:

### 4.1 Stage Positioning and Image Capture

```
Step 1: XYZ stages move to default imaging position
        (stage holder positioned vertically beneath the Thorlabs camera)
Step 2: Camera captures a snapshot of the sample plate on the stage holder
```

The stage default/park position places the plate holder directly under the camera's field of view. An optional **auto-adjustment closed loop** (`plate_auto_adjuster.py`) can fine-tune the plate centering:

```
For up to 10 iterations:
  1. camera.save_frame()                    <-- Capture current view
  2. gray_plate_on_red()                    <-- CV: find plate on red background sheet
  3. If plate fully in frame -> SUCCESS     <-- 2% margin check
  4. Translate hint to stage delta:
       "left"  -> +X (5mm)    "right" -> -X (5mm)
       "up"    -> +Y (5mm)    "down"  -> -Y (5mm)
  5. motion_service.move_axis_relative()    <-- Execute stage correction
  6. Wait for settle, loop
```

### 4.2 Spot Detection and Quality Selection

```
Step 3: CTA detection algorithm runs on the captured plate image
        - Plate region detection (Canny edge)
        - Ensemble spot detection (SimpleBlobDetector + DoH)
        - Contour refinement (local Otsu)
        - Defect classification (faint / bubble / hole)
        - Grid labeling (A1, A2, B1, B2, ...)
```

### 4.3 User Review and Final Array Decision

```
Step 4: CTA reports detection results to the user via GUI
        - Combined image: green (accepted) / red (rejected) overlay
        - Spot count summary: total detected, accepted, rejected with reasons
        - User retains FINAL DECISION on which spots to keep or skip
        - The user-confirmed array of spots becomes the measurement target list
```

This is a critical human-in-the-loop step. The algorithm provides a recommendation (accepted/rejected), but the operator makes the final call based on domain expertise and experimental requirements.

### 4.4 Coordinate Calculation and GOED Handoff

```
Step 5: CTA calculates absolute XYZ stage coordinates for each spot in the
        final array, based on:
        - Spot pixel positions (center coordinates from detection)
        - Known plate-to-stage spatial calibration
        - Current stage reference position
Step 6: The coordinate list is loaded into GOED's Array Mode as the
        execution coordinate sequence
```

The pixel-to-stage coordinate transformation converts each spot's (pixel_x, pixel_y) position into absolute (mm_X, mm_Y, mm_Z) stage coordinates that place each spot precisely at the electrochemical measurement position (e.g., under a potentiostat probe).

### 4.5 Electrochemical Measurement Sequence

```
Step 7: User uploads electrochemical measurement steps into GOED
        (e.g., CV sweeps, EIS, chronoamperometry, etc.)
Step 8: User presses "Run Sequence" in GOED
Step 9: Automated execution loop:
        For each spot coordinate in the array:
          a. XYZ stages move to the spot's absolute coordinates
          b. The FULL list of electrochemical steps executes on that spot
          c. Proceed to next spot
        Until all spots in the array are measured
```

Every spot in the array receives the identical electrochemical protocol, ensuring consistent measurement conditions across the entire sample plate.

### 4.6 Complete Workflow Diagram

```
  [Stage to Default Position]
           |
  [Camera Snapshot of Plate]
           |
  [CTA: Spot Detection + Classification]
           |
  [GUI: User Reviews Results]
  [User Confirms Final Spot Array]
           |
  [CTA: Calculate Absolute XYZ Coordinates per Spot]
           |
  [Coordinate List -> GOED Array Mode]
           |
  [User Uploads Electrochemical Steps]
           |
  [Run Sequence]
           |
     +-----+------+
     |  For each   |
     |  spot in    |
     |  array:     |
     |             |
     |  XYZ move   |
     |  to spot    |
     |      |      |
     |  Execute    |
     |  all EC     |
     |  steps      |
     |      |      |
     |  Next spot  |
     +-----+------+
           |
     [Sequence Complete]
```

---

## 5. Detection Pipeline Benchmark

Performance across three pipeline versions on two test images:

### IMG_0747.png (high-resolution, warm-toned, ~60 visible spots)

| Metric | v1 | v2 | v3 |
|--------|:---:|:---:|:---:|
| Total detected | 32 | 48 | 53 |
| Accepted | 32 | 47 | 47 |
| Rejected | 0 | 1 | 6 |

### plate.png (Thorlabs camera capture, cool-toned, lower contrast)

| Metric | v1 | v2 | v3 |
|--------|:---:|:---:|:---:|
| Total detected | 19 | 39 | 40 |
| Accepted | 19 | 39 | 37 |
| Rejected | 0 | 0 | 3 |

v3's ensemble approach improves detection recall while the three-tier rejection system (faint + bubble + hole) provides categorized quality control.

---

## 6. Strengths and Innovations

### 6.1 Adaptive, Resolution-Independent Detection

All thresholding parameters are derived from image properties (plate dimensions, contrast statistics), not hardcoded constants. The pipeline works across different cameras, zoom levels, and illumination conditions without manual tuning.

### 6.2 CLAHE Illumination Normalization

Applied before all detection, CLAHE equalizes local contrast across the plate. This is critical for non-uniform illumination (e.g., bright center, dark corners) and makes spots at different positions appear with consistent contrast.

### 6.3 Ensemble Detection with Contour Refinement

The two-detector ensemble (SimpleBlobDetector + DoH) exploits complementary strengths:
- SimpleBlobDetector excels at multi-threshold dark blob detection under illumination gradients
- DoH excels at scale-space blob detection with polarity agnosticism

The contour refinement step then extracts real spot boundaries at each detected location, giving the accuracy of contour-based analysis without the fragility of a global contour pipeline.

### 6.4 Three-Tier Defect Classification

Categorized rejection (faint / bubble / hole) provides actionable quality feedback. The faint check is a false-positive suppression mechanism that cleanly separates real deposits from detection artifacts, while bubble and hole checks assess deposit quality.

### 6.5 Closed-Loop Camera-Stage Feedback

The auto-adjustment loop demonstrates a complete sense-act cycle: the camera captures the current state, computer vision determines the correction direction, and the stage executes the move. This enables automated plate centering without manual positioning.

### 6.6 Clean Hardware Abstraction

The ABC-based hardware abstraction (`AxisController` interface) with dependency injection (`create_services(use_mock=...)`) enables full offline testing with mock controllers. The service layer provides async motion commands, Z-safety ordering, and sequence execution on top of raw GCS commands.

### 6.7 Self-Documenting Captures

Photo filenames encode all acquisition parameters (exposure, gain, white balance RGB), making every capture reproducible without a separate metadata database.

---

## 7. Key Technical Parameters (v3 Current Values)

| Category | Parameter | Value |
|----------|-----------|-------|
| Detection | Min spot area (base) | 460 px |
| Detection | Max spot area (base) | 80,000 px |
| Detection | Min circularity | 0.25 |
| Detection | Plate area cap | 2% |
| Detection | Border margin | 4% per side |
| SimpleBlobDetector | Threshold sweep | 10-220, step 5 |
| DoH | Sensitivity threshold | 0.008 |
| DoH | Sigma cap | plate_short_side / 25 |
| Rejection | Faint contrast min | 8% darker than background |
| Rejection | Bubble CV max | 0.70 |
| Rejection | Hole area min | 10% of spot area |
| Camera | Live view rate | 100 ms (10 fps) |
| Stage | Default step | 5.0 mm (auto-adjust) |
| Stage | Max velocity | 20 mm/s |
