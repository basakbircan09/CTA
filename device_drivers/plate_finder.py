import cv2
import numpy as np
import os


def gray_plate_on_red(image_path: str, margin_frac: float = 0.02, debug: bool = False):
    """
    Detect gray plate on red background and decide if it is fully in frame.

    margin_frac: fraction of red bbox size used as safe margin.
    Returns dict:
        {
          'rect_bbox': (x, y, w, h) or None,
          'output_image': img_with_rect,
          'output_display': resized_img,
          'save_path': path_to_saved_image,
          'fully_in_frame': bool,
          'move_hint': str  # 'ok', 'left', 'right', 'up', 'down', 'left_up', ...
        }
    """
    img = cv2.imread(image_path)
    if img is None:
        raise ValueError(f"Could not read image: {image_path}")

    orig = img.copy()
    hsv = cv2.cvtColor(img, cv2.COLOR_BGR2HSV)

    # ---- 1) detect red sheet (outer bbox) ----
    lower_red1 = np.array([0, 80, 80])
    upper_red1 = np.array([10, 255, 255])
    lower_red2 = np.array([170, 80, 80])
    upper_red2 = np.array([180, 255, 255])

    mask1 = cv2.inRange(hsv, lower_red1, upper_red1)
    mask2 = cv2.inRange(hsv, lower_red2, upper_red2)
    red_mask = cv2.bitwise_or(mask1, mask2)

    kernel = np.ones((5, 5), np.uint8)
    red_mask = cv2.morphologyEx(red_mask, cv2.MORPH_CLOSE, kernel, iterations=2)

    red_contours, _ = cv2.findContours(red_mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    if not red_contours:
        if debug:
            print("No red region found")
        output = orig
        h, w = output.shape[:2]
        output_display = cv2.resize(output, (w // 2, h // 2), interpolation=cv2.INTER_AREA)
        base, ext = os.path.splitext(image_path)
        save_path = base + "_checked" + ext
        cv2.imwrite(save_path, output)
        return {
            "rect_bbox": None,
            "output_image": output,
            "output_display": output_display,
            "save_path": save_path,
            "fully_in_frame": False,
            "move_hint": "no_red",
        }

    red_cnt = max(red_contours, key=cv2.contourArea)
    rx, ry, rw, rh = cv2.boundingRect(red_cnt)

    # non-red region (plate + background)
    non_red_mask = cv2.bitwise_not(red_mask)

    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    gray_blur = cv2.GaussianBlur(gray, (5, 5), 0)
    _, dark_bin = cv2.threshold(gray_blur, 150, 255, cv2.THRESH_BINARY_INV)

    plate_candidate = cv2.bitwise_and(dark_bin, dark_bin, mask=non_red_mask)
    plate_candidate = cv2.morphologyEx(plate_candidate, cv2.MORPH_CLOSE, kernel, iterations=2)

    contours, _ = cv2.findContours(plate_candidate, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

    best_rect = None
    best_area = 0

    for cnt in contours:
        area = cv2.contourArea(cnt)
        if area < 2000:
            continue
        peri = cv2.arcLength(cnt, True)
        approx = cv2.approxPolyDP(cnt, 0.02 * peri, True)
        if len(approx) != 4:
            continue
        x, y, w, h = cv2.boundingRect(approx)
        aspect = w / float(h)
        if 0.5 < aspect < 2.0 and area > best_area:
            best_area = area
            best_rect = (x, y, w, h)

    output = orig.copy()
    fully_in_frame = False
    move_hint = "no_plate"

    if best_rect is not None:
        px, py, pw, ph = best_rect
        cv2.rectangle(output, (px, py), (px + pw, py + ph), (0, 255, 0), 3)

        # ---- 2) check if plate bbox is fully inside red bbox with margin ----
        # margin in pixels, proportional to red size
        mx = margin_frac * rw
        my = margin_frac * rh

        # plate fully in if all sides inside red minus margin
        left_ok   = px     >= rx + mx
        right_ok  = px+pw  <= rx + rw - mx
        top_ok    = py     >= ry + my
        bottom_ok = py+ph  <= ry + rh - my

        fully_in_frame = left_ok and right_ok and top_ok and bottom_ok

        # ---- 3) movement suggestion based on plate center vs red center ----
        # if not fully in, suggest direction to move plate towards center
        if fully_in_frame:
            move_hint = "ok"
        else:
            # centers
            plate_cx = px + pw / 2.0
            plate_cy = py + ph / 2.0
            red_cx = rx + rw / 2.0
            red_cy = ry + rh / 2.0

            dx = plate_cx - red_cx
            dy = plate_cy - red_cy

            # if plate center is to the right of red center -> move stage right or left?
            # Here: "move left" means move plate left in image (stage motion depends on your axes).
            horiz = ""
            vert = ""

            # thresholds: 5% of red size
            thr_x = 0.05 * rw
            thr_y = 0.05 * rh

            if dx > thr_x:
                horiz = "left"   # plate too far right in image
            elif dx < -thr_x:
                horiz = "right"  # plate too far left

            if dy > thr_y:
                vert = "up"      # plate too low in image
            elif dy < -thr_y:
                vert = "down"    # plate too high

            if horiz and vert:
                move_hint = f"{horiz}_{vert}"
            elif horiz:
                move_hint = horiz
            elif vert:
                move_hint = vert
            else:
                move_hint = "adjust"

        if debug:
            print("Red bbox:", (rx, ry, rw, rh))
            print("Plate bbox:", best_rect)
            print("fully_in_frame:", fully_in_frame, "move_hint:", move_hint)

    # resize for display
    h, w = output.shape[:2]
    scale = min(1200 / w, 800 / h, 1.0)
    out_disp = cv2.resize(output, (int(w * scale), int(h * scale)), interpolation=cv2.INTER_AREA)

    base, ext = os.path.splitext(image_path)
    save_path = base + "_checked" + ext
    cv2.imwrite(save_path, output)

    return {
        "rect_bbox": best_rect,
        "output_image": output,
        "output_display": out_disp,
        "save_path": save_path,
        "fully_in_frame": bool(fully_in_frame),
        "move_hint": move_hint,
    }
