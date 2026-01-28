import cv2
import numpy as np
from pathlib import Path
from typing import Dict, List, Tuple, Any

# ================= DEFAULT SETTINGS =================
# Detection tuning
DEFAULT_MIN_SPOT_AREA = 300
DEFAULT_MAX_SPOT_AREA = 15000
DEFAULT_MIN_CIRCULARITY = 0.4

# Bubble / hole detection
DEFAULT_MAX_INTENSITY_CV = 0.3   # normalized non-uniformity threshold

# Resize
DEFAULT_RESIZE_PERCENT = 90        # for detection
DEFAULT_FINAL_DISPLAY_SCALE = 60   # for display only
# ====================================================


def resize_image(img, percent):
    h, w = img.shape[:2]
    return cv2.resize(
        img,
        (int(w * percent / 100), int(h * percent / 100)),
        interpolation=cv2.INTER_LANCZOS4
    )


def detect_plate(image):
    """Detect the plate region in the image using edge detection.

    Returns:
        Tuple of (x, y, width, height) for the plate bounding box,
        or None if no plate detected.
    """
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    blur = cv2.GaussianBlur(gray, (3, 3), 0)
    edges = cv2.Canny(blur, 45, 40)
    edges = cv2.dilate(edges, np.ones((3, 3), np.uint8), 1)

    contours, _ = cv2.findContours(edges, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    if not contours:
        return None

    plate_cnt = max(contours, key=cv2.contourArea)
    return cv2.boundingRect(plate_cnt)


def detect_spots(plate_img, min_area=DEFAULT_MIN_SPOT_AREA,
                 max_area=DEFAULT_MAX_SPOT_AREA,
                 min_circularity=DEFAULT_MIN_CIRCULARITY):
    """Detect circular spots on the plate image."""
    gray = cv2.cvtColor(plate_img, cv2.COLOR_BGR2GRAY)
    blur = cv2.GaussianBlur(gray, (5, 5), 0)

    thresh = cv2.adaptiveThreshold(
        blur, 255,
        cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
        cv2.THRESH_BINARY_INV,
        49, 3
    )

    thresh = cv2.morphologyEx(thresh, cv2.MORPH_OPEN, np.ones((3, 3), np.uint8))
    contours, _ = cv2.findContours(thresh, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

    spots = []
    for c in contours:
        area = cv2.contourArea(c)
        if not (min_area <= area <= max_area):
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
            "radius": radius
        })

    return spots


def compute_inspection_radius(spots):
    if not spots:
        return 10.0
    smallest_radius = min(s["radius"] for s in spots)
    r_ref = smallest_radius / 4.0
    r_check = 3.0 * r_ref
    return r_check


def has_bubble_or_hole(gray_plate, spot, r_check, max_intensity_cv=DEFAULT_MAX_INTENSITY_CV):
    """Check if a spot has bubbles or holes."""
    cx, cy = spot["center"]

    mask = np.zeros(gray_plate.shape, dtype=np.uint8)
    cv2.circle(mask, (cx, cy), int(r_check), 255, -1)

    values = gray_plate[mask == 255]
    if len(values) < 30:
        return True

    # --- Bubble detection (normalized) ---
    cv_val = np.std(values) / (np.mean(values) + 1e-6)
    bubble = cv_val > max_intensity_cv

    # --- Hole detection (topology) ---
    masked = cv2.bitwise_and(gray_plate, gray_plate, mask=mask)
    thresh = cv2.threshold(masked, 0, 255,
                            cv2.THRESH_BINARY + cv2.THRESH_OTSU)[1]

    cnts, hierarchy = cv2.findContours(
        thresh, cv2.RETR_CCOMP, cv2.CHAIN_APPROX_SIMPLE
    )

    hole = False
    if hierarchy is not None:
        for h in hierarchy[0]:
            if h[3] != -1:
                hole = True
                break

    return bubble or hole


def sort_and_label(spots):
    """Sort spots into rows and label them (A1, A2, B1, B2, etc.)."""
    if not spots:
        return []

    spots = sorted(spots, key=lambda s: s["center"][1])

    rows = []
    y_vals = [s["center"][1] for s in spots]
    row_thresh = np.median(np.diff(y_vals)) * 0.6 if len(y_vals) > 2 else 40

    for s in spots:
        for row in rows:
            if abs(s["center"][1] - row[0]["center"][1]) < row_thresh:
                row.append(s)
                break
        else:
            rows.append([s])

    labeled = []
    for r, row in enumerate(rows):
        row = sorted(row, key=lambda s: s["center"][0])
        for c, s in enumerate(row):
            s["label"] = f"{chr(65+r)}{c+1}"
            labeled.append(s)

    return labeled


def draw_results(image, spots, px, py, accepted_only=False):
    """Draw detection results on the image."""
    out = image.copy()
    for s in spots:
        contour = s["contour"] + [px, py]
        color = (0, 255, 0) if not accepted_only else (255, 0, 0)

        cv2.drawContours(out, [contour], -1, color, 2)

        gx, gy = s["center"][0] + px, s["center"][1] + py
        cv2.circle(out, (gx, gy), 3, (0, 0, 255), -1)
        cv2.putText(out, s["label"], (gx+5, gy-5),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.5, color, 1)
    return out


def analyze_plate_and_spots(
    image_path: str,
    save_dir: str = None,
    resize_percent: int = DEFAULT_RESIZE_PERCENT,
    min_spot_area: int = DEFAULT_MIN_SPOT_AREA,
    max_spot_area: int = DEFAULT_MAX_SPOT_AREA,
    min_circularity: float = DEFAULT_MIN_CIRCULARITY,
    max_intensity_cv: float = DEFAULT_MAX_INTENSITY_CV
) -> Dict[str, Any]:
    """
    Main analysis function for plate and spot detection.

    Args:
        image_path: Path to the image file
        save_dir: Directory to save output images (optional)
        resize_percent: Resize percentage for detection
        min_spot_area: Minimum spot area in pixels
        max_spot_area: Maximum spot area in pixels
        min_circularity: Minimum circularity (0-1)
        max_intensity_cv: Maximum intensity coefficient of variation for bubble detection

    Returns:
        Dictionary with:
        - plate_bbox: (x, y, w, h) or None
        - all_spots: List of all detected spots
        - accepted_spots: List of spots without defects
        - rejected_spots: List of spots with bubbles/holes
        - all_spots_image: Image with all spots marked
        - accepted_spots_image: Image with only accepted spots marked
        - plate_detected: Boolean
    """
    img = cv2.imread(str(image_path))
    if img is None:
        return {
            "plate_detected": False,
            "plate_bbox": None,
            "all_spots": [],
            "accepted_spots": [],
            "rejected_spots": [],
            "all_spots_image": None,
            "accepted_spots_image": None,
            "error": "Image not found"
        }

    img = resize_image(img, resize_percent)

    # Detect plate
    plate_bbox = detect_plate(img)
    if plate_bbox is None:
        return {
            "plate_detected": False,
            "plate_bbox": None,
            "all_spots": [],
            "accepted_spots": [],
            "rejected_spots": [],
            "all_spots_image": img,
            "accepted_spots_image": img,
            "error": "Plate not detected"
        }

    px, py, pw, ph = plate_bbox
    plate = img[py:py+ph, px:px+pw]
    gray_plate = cv2.cvtColor(plate, cv2.COLOR_BGR2GRAY)

    # Detect spots
    spots = detect_spots(plate, min_spot_area, max_spot_area, min_circularity)
    spots = sort_and_label(spots)

    # Check for bubbles/holes
    accepted, rejected = [], []
    if spots:
        r_check = compute_inspection_radius(spots)
        for s in spots:
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
        "plate_bbox": plate_bbox,
        "all_spots": spots,
        "accepted_spots": accepted,
        "rejected_spots": rejected,
        "all_spots_image": all_img,
        "accepted_spots_image": acc_img,
        "error": None
    }


# Legacy main() for standalone usage
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

    # Display
    all_disp = resize_image(result["all_spots_image"], DEFAULT_FINAL_DISPLAY_SCALE)
    acc_disp = resize_image(result["accepted_spots_image"], DEFAULT_FINAL_DISPLAY_SCALE)

    cv2.imshow("All detected spots", all_disp)
    cv2.imshow("Accepted spots only", acc_disp)
    cv2.waitKey(0)
    cv2.destroyAllWindows()


if __name__ == "__main__":
    main()
