# inspection.py

import cv2
import numpy as np
from typing import Dict, Any, Tuple

from .config import (
    DEFAULT_PLATE_WIDTH_MM,
    DEFAULT_MIN_SPOT_DIAMETER_MM,
    DEFAULT_ERODE_PX,
    DEFAULT_MAD_K,
    DEFAULT_MAX_OUTLIER_FRAC,
    DEFAULT_DARK_Q,
    DEFAULT_BRIGHT_Q,
    DEFAULT_DEFECT_AREA_FRAC,
    DEFAULT_MIN_DEFECT_AREA_PX,
)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def inspect_spot_defects(
    gray_norm: np.ndarray,
    spot: Dict[str, Any],
    plate_width_mm: float = DEFAULT_PLATE_WIDTH_MM,
    min_spot_diameter_mm: float = DEFAULT_MIN_SPOT_DIAMETER_MM,
    erode_px: int = DEFAULT_ERODE_PX,
    mad_k: float = DEFAULT_MAD_K,
    max_outlier_frac: float = DEFAULT_MAX_OUTLIER_FRAC,
    dark_q: float = DEFAULT_DARK_Q,
    bright_q: float = DEFAULT_BRIGHT_Q,
    defect_area_frac: float = DEFAULT_DEFECT_AREA_FRAC,
    min_defect_area_px: int = DEFAULT_MIN_DEFECT_AREA_PX,
) -> Tuple[bool, Dict[str, Any]]:
    """Inspect one spot for dark or bright defect regions.

    Strategy
    --------
    1. Compute mm_per_pixel = plate_width_mm / gray_norm.shape[1].
       Derive inspect_radius_px = (min_spot_diameter_mm / 2.0) / mm_per_pixel.
       This gives a fixed physical inspection circle (1.5 mm diameter by
       default) regardless of the actual detected spot size.
    2. Draw the inspection circle and optionally erode it inward by erode_px
       pixels to exclude edge artefacts.
    3. Compute MAD-based outlier fraction (informational only — not used for
       rejection).
    4. Build binary maps for dark pixels (≤ dark_q percentile) and bright
       pixels (≥ bright_q percentile) inside the inspection circle.
    5. Clean each binary map with a 3×3 MORPH_OPEN.
    6. Compute the inner boundary of the inspection circle (morphological
       gradient) to identify edge-touching artefacts.
    7. For each connected component in the dark/bright maps, flag it if:
       - Its area ≥ min_area threshold, AND
       - It does NOT touch the inner boundary.
    8. Flag the spot as ``is_bad`` if any valid component is found.

    Returns
    -------
    (is_bad, metrics_dict)
    """
    cx, cy = spot["center"]

    # Compute physical scale from image dimensions
    crop_width_px    = gray_norm.shape[1]
    mm_per_pixel     = plate_width_mm / crop_width_px
    inspect_radius_px = int(round((min_spot_diameter_mm / 2.0) / mm_per_pixel))

    # Draw the inspection circle
    circle_mask = np.zeros(gray_norm.shape, dtype=np.uint8)
    cv2.circle(circle_mask, (cx, cy), inspect_radius_px, 255, thickness=-1)

    # Optionally erode to exclude edge pixels
    if erode_px > 0:
        k      = 2 * erode_px + 1
        kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (k, k))
        inner  = cv2.erode(circle_mask, kernel, iterations=1)
    else:
        inner = circle_mask

    vals = gray_norm[inner == 255]

    if vals.size < 80:
        return False, {
            "reason":             [],
            "n":                  int(vals.size),
            "inspect_radius_px":  inspect_radius_px,
            "warning":            "too_few_pixels_for_reliable_defect_check",
        }

    # ---- MAD-based non-uniformity (informational only) ----
    med          = float(np.median(vals))
    mad          = float(np.median(np.abs(vals - med))) + 1e-6
    z            = np.abs(vals - med) / (1.4826 * mad)
    outlier_frac = float(np.mean(z > mad_k))
    nonuniform_flag = outlier_frac > max_outlier_frac

    # ---- Percentile thresholds ----
    t_dark   = float(np.percentile(vals, dark_q))
    t_bright = float(np.percentile(vals, bright_q))

    # ---- Binary dark / bright maps inside inspection circle ----
    dark_bin   = np.zeros_like(gray_norm, dtype=np.uint8)
    bright_bin = np.zeros_like(gray_norm, dtype=np.uint8)
    dark_bin[  (inner == 255) & (gray_norm <= t_dark)]   = 255
    bright_bin[(inner == 255) & (gray_norm >= t_bright)] = 255

    ker        = np.ones((3, 3), np.uint8)
    dark_bin   = cv2.morphologyEx(dark_bin,   cv2.MORPH_OPEN, ker)
    bright_bin = cv2.morphologyEx(bright_bin, cv2.MORPH_OPEN, ker)

    # ---- Inner boundary (components touching this are edge artefacts) ----
    inner_boundary  = cv2.morphologyEx(inner, cv2.MORPH_GRADIENT, ker)
    spot_area_inner = int(np.sum(inner == 255))
    min_area        = max(min_defect_area_px, int(defect_area_frac * spot_area_inner))

    def has_valid_component(bin_img: np.ndarray) -> bool:
        """Return True if any component is large enough and interior."""
        num, labels, stats, _ = cv2.connectedComponentsWithStats(
            bin_img, connectivity=8
        )
        if num <= 1:
            return False
        for lab in range(1, num):
            area = int(stats[lab, cv2.CC_STAT_AREA])
            if area < min_area:
                continue
            comp = (labels == lab).astype(np.uint8) * 255
            if not np.any((comp == 255) & (inner_boundary == 255)):
                return True
        return False

    # ---- Classify ----
    reasons = []
    if has_valid_component(dark_bin):
        reasons.append("dark_defect_component")
    if has_valid_component(bright_bin):
        reasons.append("bright_defect_component")

    metrics = {
        "median":             med,
        "mad":                mad,
        "outlier_frac":       outlier_frac,
        "nonuniform_flag":    nonuniform_flag,
        "t_dark":             t_dark,
        "t_bright":           t_bright,
        "min_defect_area_px": int(min_area),
        "inspect_radius_px":  inspect_radius_px,
        "n":                  int(vals.size),
        "reason":             reasons,
    }

    return len(reasons) > 0, metrics
