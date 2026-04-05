# inspection.py

import cv2
import numpy as np
from typing import Dict, Any, Tuple

from .config import (
    DEFAULT_ERODE_PX,
    DEFAULT_MAD_K,
    DEFAULT_MAX_OUTLIER_FRAC,
    DEFAULT_DARK_Q,
    DEFAULT_BRIGHT_Q,
    DEFAULT_DEFECT_AREA_FRAC,
    DEFAULT_MIN_DEFECT_AREA_PX,
)


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _spot_mask(shape_hw: tuple, contour: np.ndarray) -> np.ndarray:
    """Draw a filled contour mask onto a blank image of shape (H, W)."""
    m = np.zeros(shape_hw, dtype=np.uint8)
    cv2.drawContours(m, [contour], -1, 255, thickness=-1)
    return m


def _erode_mask(mask: np.ndarray, erode_px: int) -> np.ndarray:
    """Erode a binary mask inward by erode_px pixels (elliptical kernel).

    Shrinking the mask before extracting pixel values prevents edge artefacts
    (partial pixels at the spot boundary) from being mistaken for defects.
    """
    if erode_px <= 0:
        return mask
    k      = 2 * erode_px + 1
    kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (k, k))
    return cv2.erode(mask, kernel, iterations=1)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def inspect_spot_defects(
    gray_norm: np.ndarray,
    spot: Dict[str, Any],
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
    1. Draw the full spot contour as a filled mask, then erode inward by
       erode_px pixels so edge artefacts are excluded from analysis.
    2. Compute MAD-based outlier fraction (informational only — not used for
       rejection).
    3. Build binary maps for dark pixels (≤ dark_q percentile) and bright
       pixels (≥ bright_q percentile) inside the eroded mask.
    4. Clean each binary map with a 3×3 MORPH_OPEN to remove single-pixel
       noise.
    5. Compute the inner boundary of the eroded mask (morphological gradient)
       to identify components that merely touch the spot edge.
    6. For each connected component in the dark/bright maps, flag it if:
       - Its area ≥ min_area threshold, AND
       - It does NOT touch the inner boundary.
    7. Flag the spot as ``is_bad`` if any valid component is found.

    Returns
    -------
    (is_bad, metrics_dict)
    """
    spot_mask = _spot_mask(gray_norm.shape, spot["contour"])
    inner     = _erode_mask(spot_mask, erode_px)

    vals = gray_norm[inner == 255]

    if vals.size < 80:
        return False, {
            "reason":  [],
            "n":       int(vals.size),
            "warning": "too_few_pixels_for_reliable_defect_check",
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

    # ---- Binary dark / bright maps inside eroded mask ----
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
        "n":                  int(vals.size),
        "reason":             reasons,
    }

    return len(reasons) > 0, metrics
