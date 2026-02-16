import cv2
import numpy as np
from typing import Dict, Tuple, Any


def check_plate_spots(
    image_path: str,
    save_path: str | None = None,
    spot_area_threshold: float = 80.0,
    circle_fill_threshold: float = 0.85,
    display_result: bool = False,
) -> Dict[str, Any]:
    """
    Bubble/spot detection on glassy carbon plate.

    Steps:
      1) Roughly detect the plate as the largest mid-dark region.
      2) Inside plate, detect brighter/darker spots.
      3) For each spot, check:
         - area > spot_area_threshold
         - contour circularity
         - fill ratio vs enclosing circle
      4) Draw green circles for "good" bubbles, red for defects.

    Returns:
      {
        'plate_bbox': (x, y, w, h),
        'perfect_circle_count': int,
        'defective_count': int,
        'output_image': np.ndarray,
      }
    """
    image = cv2.imread(image_path)
    if image is None:
        raise ValueError(f"Could not load image: {image_path}")
    h, w, _ = image.shape

    # --- 1) Rough plate detection by brightness clustering ---
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    gray_blur = cv2.GaussianBlur(gray, (5, 5), 0)

    # Use k-means on gray intensities to find dominant mid-dark cluster as plate
    Z = gray_blur.reshape((-1, 1)).astype(np.float32)
    criteria = (cv2.TERM_CRITERIA_EPS + cv2.TERM_CRITERIA_MAX_ITER, 10, 1.0)
    K = 3
    _, labels, centers = cv2.kmeans(Z, K, None, criteria, 5, cv2.KMEANS_RANDOM_CENTERS)
    centers = centers.flatten()
    # Choose the cluster with median brightness as plate
    sorted_idx = np.argsort(centers)
    mid_idx = sorted_idx[len(sorted_idx) // 2]
    plate_cluster_val = centers[mid_idx]

    # Build mask for plate cluster (within some tolerance)
    tol = 25
    low = max(0, plate_cluster_val - tol)
    high = min(255, plate_cluster_val + tol)

    # Use plain NumPy boolean mask instead of cv2.inRange to avoid type issues
    plate_mask = ((gray_blur >= low) & (gray_blur <= high)).astype(np.uint8) * 255
    plate_mask = cv2.medianBlur(plate_mask, 5)
    plate_mask = cv2.morphologyEx(
        plate_mask, cv2.MORPH_CLOSE, np.ones((5, 5), np.uint8), iterations=2
    )

    contours, _ = cv2.findContours(plate_mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    if not contours:
        raise RuntimeError("No plate region found in image.")
    plate_contour = max(contours, key=cv2.contourArea)
    x, y, pw, ph = cv2.boundingRect(plate_contour)
    plate_bbox: Tuple[int, int, int, int] = (x, y, pw, ph)

    # --- 2) Extract plate ROI and find spots ---
    plate_roi = image[y:y + ph, x:x + pw]
    plate_gray = cv2.cvtColor(plate_roi, cv2.COLOR_BGR2GRAY)
    plate_gray_blur = cv2.GaussianBlur(plate_gray, (5, 5), 0)

    # Spots can be brighter or darker than plate; use absolute difference from median
    median_val = np.median(plate_gray_blur)
    diff = cv2.absdiff(plate_gray_blur, np.full_like(plate_gray_blur, median_val, dtype=np.uint8))
    _, spot_mask = cv2.threshold(diff, 25, 255, cv2.THRESH_BINARY)
    spot_mask = cv2.medianBlur(spot_mask, 5)
    spot_mask = cv2.morphologyEx(spot_mask, cv2.MORPH_OPEN, np.ones((3, 3), np.uint8), iterations=1)

    contours, _ = cv2.findContours(spot_mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    output = image.copy()

    circle_count = 0
    defect_count = 0

    for cnt in contours:
        area = cv2.contourArea(cnt)
        if area < spot_area_threshold:
            continue

        # Enclosing circle
        (cx, cy), radius = cv2.minEnclosingCircle(cnt)
        cx, cy, radius = float(cx), float(cy), float(radius)

        if radius <= 0:
            continue

        # Circularity: 4πA / P^2 close to 1 for circle
        perimeter = cv2.arcLength(cnt, True)
        if perimeter == 0:
            continue
        circularity = 4.0 * np.pi * area / (perimeter ** 2)

        # Fill ratio: area of contour vs area of its enclosing circle
        circle_area = np.pi * (radius ** 2)
        fill_ratio = area / circle_area if circle_area > 0 else 0.0

        # Good bubble if sufficiently circular and well filled
        circular_enough = circularity > 0.75
        filled_enough = fill_ratio > circle_fill_threshold

        center_global = (int(cx) + x, int(cy) + y)
        radius_int = int(radius)

        if circular_enough and filled_enough:
            # Good bubble: green circle
            cv2.circle(output, center_global, radius_int, (0, 255, 0), 2)
            circle_count += 1
        else:
            # Defect: red contour
            cnt_global = cnt + np.array([[x, y]])
            cv2.drawContours(output, [cnt_global], -1, (0, 0, 255), 2)
            defect_count += 1

    if save_path:
        cv2.imwrite(save_path, output)

    if display_result:
        cv2.imshow("WE / bubble detection", output)
        cv2.waitKey(0)
        cv2.destroyAllWindows()

    return {
        "plate_bbox": plate_bbox,
        "perfect_circle_count": circle_count,
        "defective_count": defect_count,
        "output_image": output,
    }
