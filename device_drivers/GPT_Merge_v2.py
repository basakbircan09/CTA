"""
GPT_Merge_v2  —  Improved plate & spot detection pipeline.

Drop-in replacement for GPT_Merge.py.  All thresholding parameters are
derived from the actual plate image (resolution, contrast, intensity
distribution) so the pipeline generalises across different cameras,
zoom levels, and illumination conditions.

Fixes over v1:
  1.  Canny thresholds corrected (low < high, wide hysteresis band)
  2.  Larger Gaussian blur for plate boundary detection
  3.  CLAHE illumination normalisation before spot thresholding
  4.  Adaptive block_size & C derived from plate dimensions + contrast
  5.  Area filter scaled to plate pixel area (resolution-independent)
  6.  Circularity threshold lowered to accept irregular deposits
  7.  Per-spot inspection radius (was global smallest-radius)
  8.  Otsu computed on masked pixels only (was corrupted by zero-padding)
  9.  Bubble CV threshold relaxed for textured electrochemical deposits
  10. Robust row clustering in sort_and_label()
  11. Contour dtype fix in draw_results()
  12. New plate_bbox pass-through to skip redundant plate detection
"""

import cv2
import numpy as np
from pathlib import Path
from typing import Dict, List, Tuple, Any, Optional

# ================= DEFAULT SETTINGS =================
# These are *fallback* limits.  detect_spots() auto-scales area bounds
# relative to the plate size; these are only used when the caller
# explicitly passes values.
DEFAULT_MIN_SPOT_AREA = 200
DEFAULT_MAX_SPOT_AREA = 80000
DEFAULT_MIN_CIRCULARITY = 0.25

# Bubble / hole detection
DEFAULT_MAX_INTENSITY_CV = 0.70

# Resize
DEFAULT_RESIZE_PERCENT = 100
DEFAULT_FINAL_DISPLAY_SCALE = 60
# ====================================================

# Reference plate area (px) used to normalise area bounds.
# Calibrated from a ~500 x 500 crop where spots range ~300-15 000 px.
_REF_PLATE_AREA = 500 * 500


def resize_image(img, percent):
    h, w = img.shape[:2]
    return cv2.resize(
        img,
        (int(w * percent / 100), int(h * percent / 100)),
        interpolation=cv2.INTER_LANCZOS4,
    )


# ---- Plate detection (Canny + blur) ----
def detect_plate(image):
    """Detect the plate region using edge detection.

    Returns (x, y, w, h) bounding box or None.
    """
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    blur = cv2.GaussianBlur(gray, (11, 11), 0)
    edges = cv2.Canny(blur, 30, 90)
    edges = cv2.dilate(edges, np.ones((3, 3), np.uint8), iterations=2)

    contours, _ = cv2.findContours(edges, cv2.RETR_EXTERNAL,
                                   cv2.CHAIN_APPROX_SIMPLE)
    if not contours:
        return None

    plate_cnt = max(contours, key=cv2.contourArea)
    return cv2.boundingRect(plate_cnt)


# ---- CLAHE illumination normalisation ----
def equalise_plate(gray):
    """Apply CLAHE to normalise non-uniform illumination."""
    clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
    return clahe.apply(gray)


# ---- Adaptive spot detection ----
def _compute_adaptive_params(plate_h, plate_w, gray_blur):
    """Derive block_size and C from the plate image itself.

    block_size : ~1/4 of the shorter plate dimension, clamped [21..251],
                 forced odd.  This keeps the local window large enough to
                 capture the macro illumination gradient but small enough
                 to preserve per-spot contrast.

    C          : Proportional to the local contrast energy of the plate
                 (standard-deviation of the blurred grayscale).  For
                 high-contrast images (warm IMG_0747) this is higher; for
                 low-contrast camera captures (plate.png) it is lower.
                 Clamped to [4..20].
    """
    short_side = min(plate_h, plate_w)
    bs = int(short_side / 4)
    bs = max(21, min(bs, 251))
    if bs % 2 == 0:
        bs += 1

    contrast = float(np.std(gray_blur))
    c_val = int(round(contrast * 0.22))
    c_val = max(4, min(c_val, 16))

    return bs, c_val


def _compute_area_bounds(plate_h, plate_w, min_area, max_area):
    """Scale area bounds relative to the plate linear dimension.

    Spots are physical objects — if image resolution doubles (2x each
    dimension), spot *radius* doubles and spot *area* quadruples.
    So we scale area bounds by (linear_scale)^2 = plate_area / ref_area,
    but using sqrt gives us the linear ratio which we then square:
        scale = (short_side / ref_short_side) ^ 2
    This is gentler than raw area ratio for very large images.
    """
    ref_short = int(np.sqrt(_REF_PLATE_AREA))       # ~500
    short_side = min(plate_h, plate_w)
    linear_scale = short_side / ref_short
    scale = linear_scale ** 2                        # area ratio

    scaled_min = max(int(min_area * scale), 50)
    scaled_max = max(int(max_area * scale), scaled_min * 10)

    return scaled_min, scaled_max


def detect_spots(plate_img, min_area=DEFAULT_MIN_SPOT_AREA,
                 max_area=DEFAULT_MAX_SPOT_AREA,
                 min_circularity=DEFAULT_MIN_CIRCULARITY):
    """Detect dark spots on the plate image.

    All threshold parameters are automatically derived from the plate
    image dimensions and intensity statistics.
    """
    gray = cv2.cvtColor(plate_img, cv2.COLOR_BGR2GRAY)
    gray = equalise_plate(gray)
    blur = cv2.GaussianBlur(gray, (5, 5), 0)

    plate_h, plate_w = blur.shape[:2]

    # Adaptive parameters
    block_size, c_val = _compute_adaptive_params(plate_h, plate_w, blur)
    eff_min, eff_max = _compute_area_bounds(plate_h, plate_w,
                                            min_area, max_area)

    thresh = cv2.adaptiveThreshold(
        blur, 255,
        cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
        cv2.THRESH_BINARY_INV,
        blockSize=block_size,
        C=c_val,
    )

    kernel = np.ones((3, 3), np.uint8)
    thresh = cv2.morphologyEx(thresh, cv2.MORPH_OPEN, kernel)
    thresh = cv2.morphologyEx(thresh, cv2.MORPH_CLOSE, kernel)

    contours, _ = cv2.findContours(thresh, cv2.RETR_EXTERNAL,
                                   cv2.CHAIN_APPROX_SIMPLE)

    spots = []
    for c in contours:
        area = cv2.contourArea(c)
        if not (eff_min <= area <= eff_max):
            continue

        peri = cv2.arcLength(c, True)
        if peri == 0:
            continue

        circ = 4 * np.pi * area / (peri ** 2)
        if circ < min_circularity:
            continue

        M = cv2.moments(c)
        if M["m00"] == 0:
            continue

        cx = int(M["m10"] / M["m00"])
        cy = int(M["m01"] / M["m00"])
        radius = np.sqrt(area / np.pi)

        spots.append({
            "contour": c,
            "center": (cx, cy),
            "radius": radius,
            "area": area,
            "circularity": circ,
        })

    return spots


# ---- Per-spot inspection radius ----
def compute_inspection_radius(spot):
    """Return the inspection radius for a single spot (75% of its own radius)."""
    return max(spot["radius"] * 0.75, 5.0)


# ---- Defect classification ----
def has_bubble_or_hole(gray_plate, spot, r_check,
                       max_intensity_cv=DEFAULT_MAX_INTENSITY_CV):
    """Check whether a spot contains bubbles or holes.

    Returns True if defective.
    """
    cx, cy = spot["center"]

    mask = np.zeros(gray_plate.shape, dtype=np.uint8)
    cv2.circle(mask, (cx, cy), int(r_check), 255, -1)

    values = gray_plate[mask == 255]
    if len(values) < 30:
        return True

    # --- Bubble detection (normalised CV) ---
    mean_val = np.mean(values)
    cv_val = np.std(values) / (mean_val + 1e-6)
    bubble = cv_val > max_intensity_cv

    # --- Hole detection (topology on properly-thresholded region) ---
    # Compute Otsu from the spot pixels only (not zero-padded image).
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


# ---- Robust row clustering ----
def sort_and_label(spots):
    """Sort spots into rows and label them (A1, A2, B1, B2, ...)."""
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


# ---- Draw results (dtype-safe) ----
def draw_results(image, spots, px, py, accepted_only=False):
    """Draw detection results on the image."""
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


# ---- Main pipeline ----
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
    """Main analysis: plate detection -> spot detection -> defect classification.

    Args:
        image_path:       Path to the input image.
        save_dir:         Directory to save annotated output images.
        resize_percent:   Resize percentage for detection (100 = full res).
        min_spot_area:    Base minimum contour area (auto-scaled to plate).
        max_spot_area:    Base maximum contour area (auto-scaled to plate).
        min_circularity:  Minimum 4*pi*A/P^2 ratio.
        max_intensity_cv: CV threshold for bubble detection.
        plate_bbox:       Pre-computed (x,y,w,h) to skip detect_plate().

    Returns:
        Result dict with plate_bbox, plate_image, all_spots,
        accepted_spots, rejected_spots, annotated images, error.
    """
    img = cv2.imread(str(image_path))
    if img is None:
        return {
            "plate_detected": False,
            "plate_bbox": None,
            "plate_image": None,
            "all_spots": [],
            "accepted_spots": [],
            "rejected_spots": [],
            "all_spots_image": None,
            "accepted_spots_image": None,
            "error": "Image not found",
        }

    img = resize_image(img, resize_percent)

    # Detect plate (or use provided bbox)
    if plate_bbox is not None:
        px, py, pw, ph = plate_bbox
    else:
        detected = detect_plate(img)
        if detected is None:
            return {
                "plate_detected": False,
                "plate_bbox": None,
                "plate_image": None,
                "all_spots": [],
                "accepted_spots": [],
                "rejected_spots": [],
                "all_spots_image": img,
                "accepted_spots_image": img,
                "error": "Plate not detected",
            }
        px, py, pw, ph = detected

    plate = img[py : py + ph, px : px + pw]
    gray_plate = cv2.cvtColor(plate, cv2.COLOR_BGR2GRAY)

    # Detect spots (parameters auto-scaled inside)
    spots = detect_spots(plate, min_spot_area, max_spot_area, min_circularity)
    spots = sort_and_label(spots)

    # Classify defects — per-spot inspection radius
    accepted, rejected = [], []
    for s in spots:
        r_check = compute_inspection_radius(s)
        if has_bubble_or_hole(gray_plate, s, r_check, max_intensity_cv):
            rejected.append(s)
        else:
            accepted.append(s)

    # Draw results
    all_img = draw_results(img, spots, px, py)
    acc_img = draw_results(img, accepted, px, py, accepted_only=True)

    # Save if directory provided
    if save_dir:
        save_path = Path(save_dir)
        save_path.mkdir(parents=True, exist_ok=True)
        cv2.imwrite(str(save_path / "all_detected.png"), all_img)
        cv2.imwrite(str(save_path / "accepted_only.png"), acc_img)

    return {
        "plate_detected": True,
        "plate_bbox": (px, py, pw, ph),
        "plate_image": plate,
        "all_spots": spots,
        "accepted_spots": accepted,
        "rejected_spots": rejected,
        "all_spots_image": all_img,
        "accepted_spots_image": acc_img,
        "error": None,
    }


def main():
    """Standalone test entry point."""
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
