# detection.py

import cv2
import numpy as np
from typing import Dict, Any, List, Tuple

from .config import (
    DEFAULT_BG_BLUR_K, DEFAULT_CLAHE_CLIP, DEFAULT_CLAHE_TILE,
    DEFAULT_THRESH_BLOCKSIZE, DEFAULT_THRESH_C,
    DEFAULT_OPEN_KERNEL, DEFAULT_CLOSE_KERNEL,
    DEFAULT_MIN_SPOT_AREA, DEFAULT_MAX_SPOT_AREA,
    DEFAULT_MIN_CIRCULARITY, DEFAULT_MIN_SOLIDITY,
    DEFAULT_PLATE_WIDTH_MM, DEFAULT_MIN_SPOT_DIAMETER_MM,
)


# ---------------------------------------------------------------------------
# Preprocessing
# ---------------------------------------------------------------------------

def preprocess_for_detection(bgr: np.ndarray, debug: dict = None) -> np.ndarray:
    """Convert BGR image to a normalised, contrast-enhanced grayscale image.

    Steps:
      1. Grayscale conversion
      2. Large-kernel Gaussian blur to estimate illumination background
      3. Divide-normalise to remove uneven lighting
      4. CLAHE for local contrast enhancement
    """
    gray = cv2.cvtColor(bgr, cv2.COLOR_BGR2GRAY)

    k = DEFAULT_BG_BLUR_K if DEFAULT_BG_BLUR_K % 2 else DEFAULT_BG_BLUR_K + 1
    bg = cv2.GaussianBlur(gray, (k, k), 0)
    bg = np.clip(bg, 1, 255).astype(np.uint8)

    norm = cv2.divide(gray, bg, scale=255)

    clahe = cv2.createCLAHE(
        clipLimit=DEFAULT_CLAHE_CLIP,
        tileGridSize=DEFAULT_CLAHE_TILE,
    )
    norm = clahe.apply(norm)

    if debug is not None:
        debug["gray_raw"] = gray
        debug["bg"] = bg
        debug["gray_norm"] = norm

    return norm


# ---------------------------------------------------------------------------
# Spot detection
# ---------------------------------------------------------------------------

def detect_spots(image: np.ndarray, debug: dict = None):
    """Detect circular working-electrode spots in a plate image.

    mm_per_pixel is computed dynamically as DEFAULT_PLATE_WIDTH_MM divided by
    the image width in pixels, so the physical scale adapts to any crop size.

    Returns:
        spots            – list of accepted spot dicts
        rejected         – list of candidate dicts that failed filters
        pdbg             – dict of intermediate debug images (includes
                           total_contours and mm_per_pixel)
    """
    pdbg: dict = {}
    norm = preprocess_for_detection(image, debug=pdbg)

    # Physical scale: plate width in mm / image width in pixels
    crop_width_px = image.shape[1]
    mm_per_pixel  = DEFAULT_PLATE_WIDTH_MM / crop_width_px

    blur = cv2.GaussianBlur(norm, (5, 5), 0)

    blocksize = DEFAULT_THRESH_BLOCKSIZE if DEFAULT_THRESH_BLOCKSIZE % 2 == 1 else DEFAULT_THRESH_BLOCKSIZE + 1
    thresh = cv2.adaptiveThreshold(
        blur, 255,
        cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
        cv2.THRESH_BINARY_INV,
        blocksize,
        DEFAULT_THRESH_C,
    )

    if DEFAULT_OPEN_KERNEL > 0:
        opened = cv2.morphologyEx(
            thresh,
            cv2.MORPH_OPEN,
            np.ones((DEFAULT_OPEN_KERNEL, DEFAULT_OPEN_KERNEL), np.uint8),
        )
    else:
        opened = thresh.copy()

    if DEFAULT_CLOSE_KERNEL > 0:
        closed = cv2.morphologyEx(
            opened,
            cv2.MORPH_CLOSE,
            np.ones((DEFAULT_CLOSE_KERNEL, DEFAULT_CLOSE_KERNEL), np.uint8),
        )
    else:
        closed = opened.copy()

    contours, _ = cv2.findContours(
        closed, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE
    )

    if debug is not None:
        debug.update(pdbg)
        debug["blur"]             = blur
        debug["thresh_bw"]        = thresh
        debug["opened"]           = opened
        debug["closed"]           = closed
        debug["total_contours"]   = len(contours)
        debug["mm_per_pixel"]     = mm_per_pixel
        debug["crop_width_px"]    = crop_width_px

    spots: list = []
    rejected: list = []

    for c in contours:
        area = float(cv2.contourArea(c))
        peri = float(cv2.arcLength(c, True))
        circ = 0.0 if peri <= 1e-6 else 4.0 * np.pi * area / (peri ** 2)

        hull      = cv2.convexHull(c)
        hull_area = float(cv2.contourArea(hull))
        solidity  = 0.0 if hull_area <= 1e-6 else area / hull_area

        # ---- Geometric filters ----
        reason = None
        if not (DEFAULT_MIN_SPOT_AREA <= area <= DEFAULT_MAX_SPOT_AREA):
            reason = "area"
        elif peri <= 1e-6:
            reason = "perimeter"
        elif circ < DEFAULT_MIN_CIRCULARITY:
            reason = "circularity"
        elif hull_area <= 1e-6:
            reason = "hull_area"
        elif solidity < DEFAULT_MIN_SOLIDITY:
            reason = "solidity"

        if reason:
            rejected.append({
                "contour":      c,
                "reason":       reason,
                "area":         area,
                "circularity":  circ,
                "solidity":     solidity,
                "passed_geom":  False,
                "passed_size":  False,
            })
            continue

        # ---- Physical size filter (SFC opening criterion) ----
        # Use minEnclosingCircle for a radius estimate that is stable
        # against contour irregularities.
        (_, radius_px) = cv2.minEnclosingCircle(c)
        radius_mm   = float(radius_px) * mm_per_pixel
        diameter_mm = 2.0 * radius_mm

        if diameter_mm < DEFAULT_MIN_SPOT_DIAMETER_MM:
            rejected.append({
                "contour":      c,
                "reason":       "too_small_physical",
                "area":         area,
                "circularity":  circ,
                "solidity":     solidity,
                "radius_px":    float(radius_px),
                "radius_mm":    radius_mm,
                "diameter_mm":  diameter_mm,
                "passed_geom":  True,
                "passed_size":  False,
            })
            continue

        M = cv2.moments(c)
        if M["m00"] == 0:
            rejected.append({
                "contour":     c,
                "reason":      "zero_moment",
                "area":        area,
                "circularity": circ,
                "solidity":    solidity,
                "passed_geom": True,
                "passed_size": True,
            })
            continue

        cx = int(M["m10"] / M["m00"])
        cy = int(M["m01"] / M["m00"])

        spots.append({
            "contour":      c,
            "center":       (cx, cy),
            "area":         area,
            "circularity":  circ,
            "solidity":     solidity,
            "radius_px":    float(radius_px),
            "radius_mm":    radius_mm,
            "diameter_mm":  diameter_mm,
            "passed_geom":  True,
            "passed_size":  True,
        })

    return spots, rejected, pdbg


# ---------------------------------------------------------------------------
# Grid labelling
# ---------------------------------------------------------------------------

def sort_and_label(spots: list) -> list:
    """Sort spots into rows by Y-coordinate and assign grid labels.

    Labels follow the pattern A1, A2, …, B1, B2, … where rows are
    top-to-bottom (A = top) and columns are left-to-right.

    Mutates each spot dict in-place by adding a ``"label"`` key.
    Returns the same list reordered.
    """
    if not spots:
        return spots

    by_y = sorted(spots, key=lambda s: s["center"][1])
    y_vals = [s["center"][1] for s in by_y]
    diffs = np.diff(y_vals)
    row_thresh = float(np.median(diffs) * 0.6) if len(diffs) > 1 else 40.0

    rows: list[list] = []
    for s in by_y:
        placed = False
        for row in rows:
            if abs(s["center"][1] - row[0]["center"][1]) < row_thresh:
                row.append(s)
                placed = True
                break
        if not placed:
            rows.append([s])

    labeled: list = []
    for r, row in enumerate(rows):
        for c, s in enumerate(sorted(row, key=lambda s: s["center"][0])):
            s["label"] = f"{chr(65 + r)}{c + 1}"
            labeled.append(s)

    return labeled


# ---------------------------------------------------------------------------
# Missing-spot detection
# ---------------------------------------------------------------------------

def find_missing_spots(labeled_spots: list) -> list[str]:
    """Detect gaps in the expected spot grid.

    Builds a row/column map from existing labels, determines the expected
    rectangular grid, and returns labels that are absent.

    Example: if the grid has A1, A2, A4 and B1, B2, B3 it returns ["A3"].
    """
    if not labeled_spots:
        return []

    rows: dict[str, set] = {}
    for s in labeled_spots:
        label = s.get("label", "")
        if len(label) < 2:
            continue
        row_char = label[0]
        col_str  = label[1:]
        if col_str.isdigit():
            rows.setdefault(row_char, set()).add(int(col_str))

    if not rows:
        return []

    max_col = max(max(cols) for cols in rows.values())

    missing: list[str] = []
    for row_char in sorted(rows.keys()):
        present = rows[row_char]
        for col in range(1, max_col + 1):
            if col not in present:
                missing.append(f"{row_char}{col}")

    return missing
