"""
GPT_Merge_v3 — Ensemble spot detection pipeline.

Replaces the single adaptive-threshold detector with a two-detector
ensemble that merges results from:

  1. cv2.SimpleBlobDetector  — multi-threshold sweep (handles illumination
     gradients natively by testing ~30 threshold levels).
  2. skimage.feature.blob_doh — Determinant-of-Hessian multi-scale detector
     (finds both dark-on-light and light-on-dark blobs across scales).

Shared infrastructure (plate detection, CLAHE, defect classification,
labelling, drawing) is carried forward from v2 with all fixes intact.
"""

import cv2
import numpy as np
from math import sqrt
from pathlib import Path
from typing import Dict, List, Tuple, Any, Optional

from skimage.color import rgb2gray
from skimage.feature import blob_doh

# ================= DEFAULT SETTINGS =================
DEFAULT_MIN_SPOT_AREA = 1700
DEFAULT_MAX_SPOT_AREA = 80000
DEFAULT_MIN_CIRCULARITY = 0.25

DEFAULT_MAX_INTENSITY_CV = 0.35

DEFAULT_RESIZE_PERCENT = 100
DEFAULT_FINAL_DISPLAY_SCALE = 60

# Minimum distance (px) between two blob centers to consider them
# distinct.  Closer blobs from different detectors are merged.
DEFAULT_MIN_DIST_BETWEEN = 15
# ====================================================

_REF_PLATE_AREA = 500 * 500

# Post-refinement shape thresholds — reject misshapen contours & defects
_POST_REFINE_MIN_CIRCULARITY = 0.30
_POST_REFINE_MIN_SOLIDITY = 0.60

# Minimum absolute intensity difference to consider a spot non-empty
_MIN_DEPOSIT_CONTRAST_ABS = 12


def resize_image(img, percent):
    h, w = img.shape[:2]
    return cv2.resize(
        img,
        (int(w * percent / 100), int(h * percent / 100)),
        interpolation=cv2.INTER_LANCZOS4,
    )


# ------------------------------------------------------------------ #
#  Plate detection (same as v2)
# ------------------------------------------------------------------ #
def detect_plate(image):
    """Detect plate region via Canny edge detection.

    Returns (x, y, w, h) or None.
    """
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    blur = cv2.GaussianBlur(gray, (11, 11), 0)
    edges = cv2.Canny(blur, 30, 90)
    edges = cv2.dilate(edges, np.ones((3, 3), np.uint8), iterations=2)

    contours, _ = cv2.findContours(edges, cv2.RETR_EXTERNAL,
                                   cv2.CHAIN_APPROX_SIMPLE)
    if not contours:
        return None
    return cv2.boundingRect(max(contours, key=cv2.contourArea))


# ------------------------------------------------------------------ #
#  CLAHE illumination normalisation
# ------------------------------------------------------------------ #
def equalise_plate(gray):
    clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
    return clahe.apply(gray)


# ------------------------------------------------------------------ #
#  Adaptive parameter helpers (carried from v2)
# ------------------------------------------------------------------ #
def _compute_area_bounds(plate_h, plate_w, min_area, max_area):
    ref_short = int(np.sqrt(_REF_PLATE_AREA))
    short_side = min(plate_h, plate_w)
    scale = (short_side / ref_short) ** 2

    scaled_min = max(int(min_area * scale), 50)
    scaled_max = max(int(max_area * scale), scaled_min * 10)

    # No single spot should exceed ~2% of the plate area.
    # This prevents DoH from reporting plate-scale structures as blobs.
    plate_area = plate_h * plate_w
    abs_max = int(plate_area * 0.02)
    scaled_max = min(scaled_max, abs_max)
    scaled_max = max(scaled_max, scaled_min)  # ensure eff_max >= eff_min

    return scaled_min, scaled_max


# ------------------------------------------------------------------ #
#  Helper: build a synthetic circular contour from a centre + radius
# ------------------------------------------------------------------ #
def _circle_contour(cx: int, cy: int, radius: float, n_pts: int = 32):
    """Return an OpenCV-compatible contour (N,1,2) int32 polygon."""
    radius = max(radius, 2.0)  # prevent degenerate contour for tiny blobs
    angles = np.linspace(0, 2 * np.pi, n_pts, endpoint=False)
    pts = np.stack([
        cx + (radius * np.cos(angles)),
        cy + (radius * np.sin(angles)),
    ], axis=-1).round().astype(np.int32)
    return pts.reshape(-1, 1, 2)


# ------------------------------------------------------------------ #
#  Helper: contour solidity (area / convex-hull area)
# ------------------------------------------------------------------ #
def _contour_solidity(contour):
    """Return area / convex_hull_area.  Synthetic circles return 1.0."""
    area = cv2.contourArea(contour)
    if area < 1:
        return 0.0
    hull = cv2.convexHull(contour)
    hull_area = cv2.contourArea(hull)
    if hull_area < 1:
        return 0.0
    return area / hull_area


# ------------------------------------------------------------------ #
#  Detector 1 — SimpleBlobDetector (multi-threshold sweep)
# ------------------------------------------------------------------ #
def _detect_blob_detector(gray, eff_min, eff_max, min_circ):
    """Run cv2.SimpleBlobDetector and return a list of spot dicts."""
    params = cv2.SimpleBlobDetector_Params()

    # Threshold sweep — the core advantage over single-pass threshold
    params.minThreshold = 10
    params.maxThreshold = 220
    params.thresholdStep = 5

    # Both polarities — DoH already covers both; unrestricting improves
    # edge-well recall where illumination can invert contrast.
    params.filterByColor = False

    # Area filter — use 0.7x eff_min for better recall on smaller/edge spots;
    # post-detection filters (shape, empty_well, faint) handle precision.
    params.filterByArea = True
    params.minArea = float(eff_min * 0.7)
    params.maxArea = float(eff_max)

    # Circularity filter
    params.filterByCircularity = True
    params.minCircularity = float(min_circ)

    # Relaxed convexity — electrochemical spots can be concave
    params.filterByConvexity = True
    params.minConvexity = 0.3

    # Relaxed inertia — allows elongated spots
    params.filterByInertia = True
    params.minInertiaRatio = 0.15

    params.minDistBetweenBlobs = float(DEFAULT_MIN_DIST_BETWEEN)

    detector = cv2.SimpleBlobDetector_create(params)
    keypoints = detector.detect(gray)

    spots = []
    for kp in keypoints:
        cx = int(round(kp.pt[0]))
        cy = int(round(kp.pt[1]))
        radius = kp.size / 2.0
        area = np.pi * radius ** 2

        spots.append({
            "contour": _circle_contour(cx, cy, radius),
            "center": (cx, cy),
            "radius": radius,
            "area": area,
            "circularity": 1.0,
            "_source": "blob",
        })

    return spots


# ------------------------------------------------------------------ #
#  Detector 2 — scikit-image DoH (multi-scale, both polarities)
# ------------------------------------------------------------------ #
def _detect_doh(gray, eff_min, eff_max):
    """Run skimage.feature.blob_doh and return a list of spot dicts."""
    # Convert area bounds to sigma bounds for DoH
    # blob_doh returns (y, x, sigma) where the blob radius ~ sigma * sqrt(2)
    min_r = max(sqrt(eff_min / np.pi), 3)
    max_r = sqrt(eff_max / np.pi)
    min_sigma = max(min_r / sqrt(2), 1)
    max_sigma = max(max_r / sqrt(2), min_sigma + 1)

    # Cap max_sigma so DoH doesn't find plate-scale structures.
    # A spot shouldn't span more than ~8% of the plate short side.
    short_side = min(gray.shape[:2])
    sigma_cap = short_side / 25.0
    max_sigma = min(max_sigma, max(sigma_cap, min_sigma + 1))

    # blob_doh expects float image in [0, 1]
    img_float = gray.astype(np.float64) / 255.0

    try:
        blobs = blob_doh(
            img_float,
            min_sigma=max(1, int(min_sigma)),
            max_sigma=max(int(min_sigma) + 1, min(200, int(max_sigma))),
            num_sigma=15,
            threshold=0.008,
        )
    except Exception:
        blobs = np.empty((0, 3))

    spots = []
    for blob in blobs:
        y, x, sigma = blob
        cx = int(round(x))
        cy = int(round(y))
        radius = sigma * sqrt(2)
        area = np.pi * radius ** 2

        # Skip if outside area bounds (0.7x for better recall, matching blob detector)
        if area < eff_min * 0.7 or area > eff_max:
            continue

        spots.append({
            "contour": _circle_contour(cx, cy, radius),
            "center": (cx, cy),
            "radius": radius,
            "area": area,
            "circularity": 1.0,
            "_source": "doh",
        })

    return spots


# ------------------------------------------------------------------ #
#  Ensemble merge — union + deduplication
# ------------------------------------------------------------------ #
def _merge_spots(spots_a, spots_b, min_dist=None):
    """Merge two spot lists, deduplicating by proximity.

    For every pair of spots from A and B that are closer than min_dist,
    keep the one with the larger area (more confidently detected).
    """
    if min_dist is None:
        min_dist = DEFAULT_MIN_DIST_BETWEEN

    merged = [dict(s) for s in spots_a]   # deep-copy dicts to avoid mutation

    for sb in spots_b:
        bx, by = sb["center"]
        duplicate = False
        for i, sa in enumerate(merged):
            ax, ay = sa["center"]
            dist = sqrt((bx - ax) ** 2 + (by - ay) ** 2)
            if dist < min_dist:
                # Replace with the larger detection (don't mutate in place)
                if sb["area"] > sa["area"]:
                    merged[i] = dict(sb)
                duplicate = True
                break
        if not duplicate:
            merged.append(dict(sb))

    return merged


# ------------------------------------------------------------------ #
#  Contour refinement — extract real contour at each detected location
# ------------------------------------------------------------------ #
def _refine_contour(gray, spot, eff_min, eff_max):
    """Replace a synthetic circular contour with the real spot boundary.

    Uses local Otsu thresholding in a ROI around the detected centre,
    then picks the contour closest to the expected location and size.
    Falls back to the original synthetic contour if no valid contour found.
    """
    cx, cy = spot["center"]
    r = max(int(spot["radius"] * 1.5), 10)  # search region = 1.5x radius
    h, w = gray.shape[:2]

    # Clip ROI to image bounds
    x0 = max(cx - r, 0)
    y0 = max(cy - r, 0)
    x1 = min(cx + r, w)
    y1 = min(cy + r, h)

    roi = gray[y0:y1, x0:x1]
    if roi.size < 30:
        return spot  # ROI too small, keep synthetic contour

    # Local Otsu threshold within ROI
    blur = cv2.GaussianBlur(roi, (5, 5), 0)
    _, thresh = cv2.threshold(blur, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)

    # Morphological cleanup
    kernel = np.ones((3, 3), np.uint8)
    thresh = cv2.morphologyEx(thresh, cv2.MORPH_OPEN, kernel)
    thresh = cv2.morphologyEx(thresh, cv2.MORPH_CLOSE, kernel)

    contours, _ = cv2.findContours(thresh, cv2.RETR_EXTERNAL,
                                   cv2.CHAIN_APPROX_SIMPLE)
    if not contours:
        return spot

    # Pick the contour whose centroid is closest to the detected centre
    # and whose area is within bounds
    best = None
    best_dist = float("inf")
    local_cx, local_cy = cx - x0, cy - y0  # centre in ROI coords

    for c in contours:
        area = cv2.contourArea(c)
        if not (eff_min * 0.3 <= area <= eff_max * 1.5):
            continue

        M = cv2.moments(c)
        if M["m00"] == 0:
            continue
        mcx = int(M["m10"] / M["m00"])
        mcy = int(M["m01"] / M["m00"])

        dist = sqrt((mcx - local_cx) ** 2 + (mcy - local_cy) ** 2)
        if dist < best_dist:
            best_dist = dist
            best = c

    if best is None or best_dist > spot["radius"] * 1.2:
        return spot  # no close-enough contour found, keep synthetic

    # Shift contour from ROI coords back to plate coords
    offset = np.array([[[x0, y0]]], dtype=np.int32)
    real_contour = best + offset

    # Recompute spot properties from real contour
    area = cv2.contourArea(real_contour)
    peri = cv2.arcLength(real_contour, True)
    circ = 4 * np.pi * area / (peri ** 2) if peri > 0 else 0.0
    solidity = _contour_solidity(real_contour)

    # Quality gate: only accept the refined contour if it's well-shaped.
    # Thresholds match _POST_REFINE_MIN_* to avoid gate/filter gap.
    if circ < _POST_REFINE_MIN_CIRCULARITY or solidity < _POST_REFINE_MIN_SOLIDITY or area > eff_max * 1.2:
        return spot

    M = cv2.moments(real_contour)
    if M["m00"] == 0:
        return spot
    new_cx = int(M["m10"] / M["m00"])
    new_cy = int(M["m01"] / M["m00"])
    new_radius = sqrt(area / np.pi)

    spot["contour"] = real_contour.astype(np.int32)
    spot["center"] = (new_cx, new_cy)
    spot["radius"] = new_radius
    spot["area"] = area
    spot["circularity"] = circ
    return spot


# ------------------------------------------------------------------ #
#  Top-level detect_spots (ensemble)
# ------------------------------------------------------------------ #
def detect_spots(plate_img,
                 min_area=DEFAULT_MIN_SPOT_AREA,
                 max_area=DEFAULT_MAX_SPOT_AREA,
                 min_circularity=DEFAULT_MIN_CIRCULARITY):
    """Ensemble spot detection: SimpleBlobDetector + DoH, merged."""
    gray = cv2.cvtColor(plate_img, cv2.COLOR_BGR2GRAY)
    gray = equalise_plate(gray)

    plate_h, plate_w = gray.shape[:2]
    eff_min, eff_max = _compute_area_bounds(plate_h, plate_w, min_area, max_area)

    # Adaptive min_dist: ~1/40 of plate short side, clamped
    min_dist = max(int(min(plate_h, plate_w) / 40), 8)

    # Run both detectors
    spots_blob = _detect_blob_detector(gray, eff_min, eff_max, min_circularity)
    spots_doh = _detect_doh(gray, eff_min, eff_max)

    # Merge
    spots = _merge_spots(spots_blob, spots_doh, min_dist)

    # Exclude spots whose centre falls within a 1% border margin.
    # Only excludes crop-boundary artifacts; 4% was cutting edge wells.
    margin_x = int(plate_w * 0.01)
    margin_y = int(plate_h * 0.01)
    spots = [s for s in spots
             if margin_x <= s["center"][0] <= plate_w - margin_x
             and margin_y <= s["center"][1] <= plate_h - margin_y]

    # Preserve pre-refinement radius for bubble inspection later
    for s in spots:
        s["_original_radius"] = s["radius"]

    # Refine: replace synthetic circular contours with real spot boundaries
    spots = [_refine_contour(gray, s, eff_min, eff_max) for s in spots]

    # Post-refinement area filter — refined contours may shrink or expand.
    # Upper bound catches defect blobs that expanded past eff_max during refinement.
    spots = [s for s in spots if eff_min * 0.5 <= s["area"] <= eff_max]

    # Post-refinement shape filter — reject misshapen contours & defects.
    # Synthetic circles (circularity=1.0, solidity=1.0) always pass.
    spots = [s for s in spots
             if s.get("circularity", 1.0) >= _POST_REFINE_MIN_CIRCULARITY
             and _contour_solidity(s["contour"]) >= _POST_REFINE_MIN_SOLIDITY]

    return spots


# ------------------------------------------------------------------ #
#  Per-spot inspection radius
# ------------------------------------------------------------------ #
def compute_inspection_radius(spot):
    """Use pre-refinement radius * 0.75 so bubble check isn't defeated by slim refinement."""
    r = spot.get("_original_radius", spot["radius"])
    return max(r * 0.75, 5.0)


# ------------------------------------------------------------------ #
#  Defect classification — three independent checks
# ------------------------------------------------------------------ #
DEFAULT_MIN_CONTRAST = 0.08   # spot must be >= 10% darker than background

def has_bubble_or_hole(gray_plate, spot, r_check,
                       max_intensity_cv=DEFAULT_MAX_INTENSITY_CV):
    """Check whether a spot has bubbles (high CV) or holes (inner contours)."""
    cx, cy = spot["center"]

    mask = np.zeros(gray_plate.shape, dtype=np.uint8)
    cv2.circle(mask, (cx, cy), int(r_check), 255, -1)

    values = gray_plate[mask == 255]
    if len(values) < 30:
        return True

    cv_val = np.std(values) / (np.mean(values) + 1e-6)
    bubble = cv_val > max_intensity_cv

    otsu_thresh, _ = cv2.threshold(
        values.astype(np.uint8), 0, 255,
        cv2.THRESH_BINARY + cv2.THRESH_OTSU,
    )
    _, thresh_img = cv2.threshold(
        gray_plate, int(otsu_thresh), 255, cv2.THRESH_BINARY,
    )
    thresh_img = cv2.bitwise_and(thresh_img, thresh_img, mask=mask)

    cnts, hierarchy = cv2.findContours(
        thresh_img, cv2.RETR_CCOMP, cv2.CHAIN_APPROX_SIMPLE,
    )

    hole = False
    if hierarchy is not None:
        spot_area = np.pi * r_check ** 2
        for i, h in enumerate(hierarchy[0]):
            if h[3] != -1:
                inner_area = cv2.contourArea(cnts[i])
                if inner_area > 0.10 * spot_area:
                    hole = True
                    break

    return bubble or hole


def is_too_faint(gray_plate, spot, min_contrast=DEFAULT_MIN_CONTRAST,
                 plate_bg_mean=None):
    """Check whether a spot is too faint relative to its local background.

    Compares the mean intensity inside the spot to a ring around it.
    For edge wells where the ring extends past the plate boundary (ring
    starvation), falls back to *plate_bg_mean* instead of rejecting.
    Returns True if the spot is not noticeably darker than the background.
    """
    cx, cy = spot["center"]
    r_inner = max(int(spot["radius"]), 3)
    r_outer = int(r_inner * 2.0)
    h, w = gray_plate.shape[:2]

    # Inner mask (the spot itself)
    inner_mask = np.zeros((h, w), dtype=np.uint8)
    cv2.circle(inner_mask, (cx, cy), r_inner, 255, -1)

    # Outer ring mask (background around the spot)
    outer_mask = np.zeros((h, w), dtype=np.uint8)
    cv2.circle(outer_mask, (cx, cy), r_outer, 255, -1)
    ring_mask = cv2.subtract(outer_mask, inner_mask)

    inner_vals = gray_plate[inner_mask == 255]
    ring_vals = gray_plate[ring_mask == 255]

    # Inner check: need enough pixels inside the spot
    if len(inner_vals) < 10:
        return True  # not enough pixels to judge

    mean_inner = float(np.mean(inner_vals))

    # Ring check: for edge wells the ring may extend past the plate boundary.
    # Fall back to global plate background mean when ring is starved.
    if len(ring_vals) < 10:
        if plate_bg_mean is not None:
            mean_bg = plate_bg_mean
        else:
            return True  # no fallback available
    else:
        mean_bg = float(np.mean(ring_vals))

    # Spot should be darker than background.
    # contrast = (bg - spot) / bg; higher = darker spot = good.
    if mean_bg < 1e-6:
        return True
    contrast = (mean_bg - mean_inner) / mean_bg

    return contrast < min_contrast


# ------------------------------------------------------------------ #
#  Empty-well discrimination
# ------------------------------------------------------------------ #
def _compute_plate_background_mean(gray_plate, spots):
    """Return the mean intensity of plate pixels outside all detected spots."""
    mask = np.ones(gray_plate.shape, dtype=np.uint8) * 255
    for s in spots:
        cx, cy = s["center"]
        r = max(int(s["radius"]), 3)
        cv2.circle(mask, (cx, cy), r, 0, -1)
    bg_vals = gray_plate[mask == 255]
    if len(bg_vals) == 0:
        return float(np.mean(gray_plate))
    return float(np.mean(bg_vals))


def is_empty_well(gray_plate, spot, plate_bg_mean):
    """Return True if the spot has no deposited material (empty well).

    A real deposit must be sufficiently *darker* than the plate background.
    Returns True if the darkening is below *_MIN_DEPOSIT_CONTRAST_ABS*,
    or if the spot is lighter than background (not a deposit at all).
    """
    cx, cy = spot["center"]
    r = max(int(spot["radius"]), 3)
    h, w = gray_plate.shape[:2]

    mask = np.zeros((h, w), dtype=np.uint8)
    cv2.circle(mask, (cx, cy), r, 255, -1)
    vals = gray_plate[mask == 255]
    if len(vals) < 10:
        return True  # too few pixels — treat as empty
    mean_spot = float(np.mean(vals))
    # Directional: spot must be darker than background by the threshold.
    # If spot is lighter than background, (bg - spot) is negative → empty.
    return (plate_bg_mean - mean_spot) < _MIN_DEPOSIT_CONTRAST_ABS


# ------------------------------------------------------------------ #
#  Robust row clustering (same as v2)
# ------------------------------------------------------------------ #
def sort_and_label(spots):
    if not spots:
        return []

    spots = sorted(spots, key=lambda s: s["center"][1])

    y_vals = [s["center"][1] for s in spots]
    if len(y_vals) > 2:
        diffs = np.diff(y_vals)
        row_thresh = max(np.percentile(diffs, 75) * 1.2, 15)
    else:
        row_thresh = 40

    rows: List[list] = []
    for s in spots:
        placed = False
        for row in rows:
            row_mean_y = np.mean([r["center"][1] for r in row])
            if abs(s["center"][1] - row_mean_y) < row_thresh:
                row.append(s)
                placed = True
                break
        if not placed:
            rows.append([s])

    labeled = []
    for r, row in enumerate(rows):
        row = sorted(row, key=lambda s: s["center"][0])
        for c, s in enumerate(row):
            s["label"] = f"{chr(65 + r)}{c + 1}"
            labeled.append(s)

    return labeled


# ------------------------------------------------------------------ #
#  Draw results (dtype-safe, same as v2)
# ------------------------------------------------------------------ #
def draw_results(image, spots, px, py, accepted_only=False):
    out = image.copy()
    offset = np.array([[[px, py]]], dtype=np.int32)

    for s in spots:
        contour = (s["contour"] + offset).astype(np.int32)
        color = (0, 255, 0) if not accepted_only else (255, 0, 0)
        cv2.drawContours(out, [contour], -1, color, 2)

        gx, gy = s["center"][0] + px, s["center"][1] + py
        cv2.circle(out, (gx, gy), 3, (0, 0, 255), -1)
        cv2.putText(out, s["label"], (gx + 5, gy - 5),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.5, color, 1)
    return out


def draw_combined(image, accepted, rejected, px, py):
    """Draw accepted (green) and rejected (red) spots on a single image."""
    out = image.copy()
    offset = np.array([[[px, py]]], dtype=np.int32)

    # Draw rejected first (red) so accepted (green) draws on top
    for s in rejected:
        contour = (s["contour"] + offset).astype(np.int32)
        cv2.drawContours(out, [contour], -1, (0, 0, 255), 2)
        gx, gy = s["center"][0] + px, s["center"][1] + py
        cv2.circle(out, (gx, gy), 3, (0, 0, 255), -1)
        cv2.putText(out, s["label"], (gx + 5, gy - 5),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 0, 255), 1)

    for s in accepted:
        contour = (s["contour"] + offset).astype(np.int32)
        cv2.drawContours(out, [contour], -1, (0, 255, 0), 2)
        gx, gy = s["center"][0] + px, s["center"][1] + py
        cv2.circle(out, (gx, gy), 3, (0, 0, 255), -1)
        cv2.putText(out, s["label"], (gx + 5, gy - 5),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 1)

    return out


# ------------------------------------------------------------------ #
#  Main pipeline
# ------------------------------------------------------------------ #
def analyze_plate_and_spots(
    image_path: str,
    save_dir: str = None,
    resize_percent: int = DEFAULT_RESIZE_PERCENT,
    min_spot_area: int = DEFAULT_MIN_SPOT_AREA,
    max_spot_area: int = DEFAULT_MAX_SPOT_AREA,
    min_circularity: float = DEFAULT_MIN_CIRCULARITY,
    max_intensity_cv: float = DEFAULT_MAX_INTENSITY_CV,
    plate_bbox: Optional[Tuple[int, int, int, int]] = None,
) -> Dict[str, Any]:
    """Main analysis: plate detect -> ensemble spot detect -> classify -> label."""
    img = cv2.imread(str(image_path))
    if img is None:
        return {
            "plate_detected": False, "plate_bbox": None,
            "plate_image": None, "all_spots": [],
            "accepted_spots": [], "rejected_spots": [],
            "all_spots_image": None, "accepted_spots_image": None,
            "combined_image": None, "error": "Image not found",
        }

    img = resize_image(img, resize_percent)

    if plate_bbox is not None:
        px, py, pw, ph = plate_bbox
    else:
        detected = detect_plate(img)
        if detected is None:
            return {
                "plate_detected": False, "plate_bbox": None,
                "plate_image": None, "all_spots": [],
                "accepted_spots": [], "rejected_spots": [],
                "all_spots_image": img, "accepted_spots_image": img,
                "combined_image": img, "error": "Plate not detected",
            }
        px, py, pw, ph = detected

    plate = img[py : py + ph, px : px + pw]
    gray_plate = cv2.cvtColor(plate, cv2.COLOR_BGR2GRAY)

    # Ensemble spot detection
    spots = detect_spots(plate, min_spot_area, max_spot_area, min_circularity)

    # Pre-filter: remove non-spots (empty wells, faint/noise) BEFORE labeling.
    # These false detections would otherwise create phantom rows in the grid.
    plate_bg_mean = _compute_plate_background_mean(gray_plate, spots)
    spots = [s for s in spots
             if not is_empty_well(gray_plate, s, plate_bg_mean)
             and not is_too_faint(gray_plate, s, plate_bg_mean=plate_bg_mean)]

    # Label only real spots — clean grid without phantom rows
    spots = sort_and_label(spots)

    # Defect classification: bubble/hole check on real spots
    accepted, rejected = [], []
    for s in spots:
        r_check = compute_inspection_radius(s)
        if has_bubble_or_hole(gray_plate, s, r_check, max_intensity_cv):
            s["_reject_reason"] = "bubble_or_hole"
            rejected.append(s)
        else:
            accepted.append(s)

    # Draw
    all_img = draw_results(img, spots, px, py)
    acc_img = draw_results(img, accepted, px, py, accepted_only=True)
    combined_img = draw_combined(img, accepted, rejected, px, py)

    if save_dir:
        save_path = Path(save_dir)
        save_path.mkdir(parents=True, exist_ok=True)
        cv2.imwrite(str(save_path / "all_detected.png"), all_img)
        cv2.imwrite(str(save_path / "accepted_only.png"), acc_img)
        cv2.imwrite(str(save_path / "combined.png"), combined_img)

    return {
        "plate_detected": True,
        "plate_bbox": (px, py, pw, ph),
        "plate_image": plate,
        "all_spots": spots,
        "accepted_spots": accepted,
        "rejected_spots": rejected,
        "all_spots_image": all_img,
        "accepted_spots_image": acc_img,
        "combined_image": combined_img,
        "error": None,
    }


def main():
    IMAGE_PATH = r"C:\Users\Monster\Desktop\tez\GC-Pics\ourTry\last\last14.jpg"
    OUT_DIR = r"C:\Users\Monster\Desktop\tez\GC-Pics\ourTry\last"

    result = analyze_plate_and_spots(IMAGE_PATH, OUT_DIR)

    if not result["plate_detected"]:
        print(f"Error: {result['error']}")
        return

    print(f"Detected {len(result['all_spots'])} spots")
    print(f"Accepted: {len(result['accepted_spots'])}")
    print(f"Rejected: {len(result['rejected_spots'])}")

    all_disp = resize_image(result["all_spots_image"], DEFAULT_FINAL_DISPLAY_SCALE)
    acc_disp = resize_image(result["accepted_spots_image"], DEFAULT_FINAL_DISPLAY_SCALE)

    cv2.imshow("All detected spots", all_disp)
    cv2.imshow("Accepted spots only", acc_disp)
    cv2.waitKey(0)
    cv2.destroyAllWindows()


if __name__ == "__main__":
    main()
