import cv2
import numpy as np
from pathlib import Path

# ================= USER SETTINGS =================
IMAGE_PATH = r"C:\Users\Monster\Desktop\tez\GC-Pics\ourTry\last\last14.jpg"

OUT_ALL = r"C:\Users\Monster\Desktop\tez\GC-Pics\ourTry\last\all_detected.png"
OUT_ACCEPTED = r"C:\Users\Monster\Desktop\tez\GC-Pics\ourTry\last\accepted_only.png"

# Detection tuning
MIN_SPOT_AREA = 300
MAX_SPOT_AREA = 15000
MIN_CIRCULARITY = 0.4

# Bubble / hole detection (NEW)
MAX_INTENSITY_CV = 0.3   # normalized non-uniformity threshold

# Resize
RESIZE_PERCENT = 90        # for detection
FINAL_DISPLAY_SCALE = 60   # for display only
# =================================================


def resize_image(img, percent):
    h, w = img.shape[:2]
    return cv2.resize(
        img,
        (int(w * percent / 100), int(h * percent / 100)),
        interpolation=cv2.INTER_LANCZOS4
    )


def detect_plate(image):
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    blur = cv2.GaussianBlur(gray, (3, 3), 0)
    edges = cv2.Canny(blur, 45, 40)
    edges = cv2.dilate(edges, np.ones((3, 3), np.uint8), 1)

    contours, _ = cv2.findContours(edges, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    if not contours:
        raise RuntimeError("Plate not detected")

    plate_cnt = max(contours, key=cv2.contourArea)
    return cv2.boundingRect(plate_cnt)


def detect_spots(plate_img):
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
        if not (MIN_SPOT_AREA <= area <= MAX_SPOT_AREA):
            continue

        peri = cv2.arcLength(c, True)
        if peri == 0:
            continue

        circ = 4 * np.pi * area / (peri ** 2)
        if circ < MIN_CIRCULARITY:
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
    smallest_radius = min(s["radius"] for s in spots)
    r_ref = smallest_radius / 4.0
    r_check = 3.0 * r_ref
    return r_check


def has_bubble_or_hole(gray_plate, spot, r_check):
    cx, cy = spot["center"]

    mask = np.zeros(gray_plate.shape, dtype=np.uint8)
    cv2.circle(mask, (cx, cy), int(r_check), 255, -1)

    values = gray_plate[mask == 255]
    if len(values) < 30:
        return True

    # --- Bubble detection (normalized) ---
    cv_val = np.std(values) / (np.mean(values) + 1e-6)
    bubble = cv_val > MAX_INTENSITY_CV

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


def draw(image, spots, px, py, accepted_only=False):
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


def main():
    img = cv2.imread(IMAGE_PATH)
    if img is None:
        raise FileNotFoundError("Image not found")

    img = resize_image(img, RESIZE_PERCENT)

    px, py, pw, ph = detect_plate(img)
    plate = img[py:py+ph, px:px+pw]
    gray_plate = cv2.cvtColor(plate, cv2.COLOR_BGR2GRAY)

    spots = detect_spots(plate)
    spots = sort_and_label(spots)

    r_check = compute_inspection_radius(spots)

    accepted, rejected = [], []
    for s in spots:
        if has_bubble_or_hole(gray_plate, s, r_check):
            rejected.append(s)
        else:
            accepted.append(s)

    all_img = draw(img, spots, px, py)
    acc_img = draw(img, accepted, px, py, accepted_only=True)

    # ---------- FINAL DISPLAY RESIZE BLOCK ----------
    all_img_disp = resize_image(all_img, FINAL_DISPLAY_SCALE)
    acc_img_disp = resize_image(acc_img, FINAL_DISPLAY_SCALE)
    # -----------------------------------------------

    cv2.imwrite(OUT_ALL, all_img)
    cv2.imwrite(OUT_ACCEPTED, acc_img)

    cv2.imshow("All detected spots", all_img_disp)
    cv2.imshow("Accepted spots only", acc_img_disp)
    cv2.waitKey(0)
    cv2.destroyAllWindows()


if __name__ == "__main__":
    main()
