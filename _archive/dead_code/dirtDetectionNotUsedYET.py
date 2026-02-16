import cv2
import numpy as np

# ------------ PARAMETERS YOU WILL TUNE ------------
IMAGE_PATH = r"C:\Users\Monster\Desktop\tez\GC-Pics\ourTry\last\last14.jpg"
OUTPUT_PATH = r"C:\Users\Monster\Desktop\tez\GC-Pics\ourTry\last\last14_dirtDetectionCode.jpg"

# dirt blob area limits (pixels)
MIN_DIRT_AREA = 1200      # increase to ignore tiny specks
MAX_DIRT_AREA = 20000     # decrease if you want to ignore big stains

# circularity threshold (0–1); higher = more circular only
MIN_CIRCULARITY = 0.2

# preprocessing / threshold params
BLUR_KSIZE = 53           # must be odd
THRESH_BLOCK_SIZE = 39   # must be odd, >1
THRESH_C = 7

# HSV red thresholds (for red background)
LOWER_RED1 = (0, 70, 50)
UPPER_RED1 = (10, 255, 255)
LOWER_RED2 = (170, 70, 50)
UPPER_RED2 = (180, 255, 255)
# -------------------------------------------------

img = cv2.imread(IMAGE_PATH)
if img is None:
    raise IOError("Cannot read image")

h, w = img.shape[:2]

# 1) Find mirror region (largest non-red rectangle)
hsv = cv2.cvtColor(img, cv2.COLOR_BGR2HSV)
mask1 = cv2.inRange(hsv, LOWER_RED1, UPPER_RED1)
mask2 = cv2.inRange(hsv, LOWER_RED2, UPPER_RED2)
red_mask = cv2.bitwise_or(mask1, mask2)

non_red = cv2.bitwise_not(red_mask)

kernel_bg = cv2.getStructuringElement(cv2.MORPH_RECT, (5, 5))
non_red_clean = cv2.morphologyEx(non_red, cv2.MORPH_OPEN, kernel_bg, iterations=1)

contours_bg, _ = cv2.findContours(non_red_clean, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

mirror_rect = (0, 0, w, h)
max_area = 0
for cnt in contours_bg:
    x, y, ww, hh = cv2.boundingRect(cnt)
    area = ww * hh
    if area > max_area:
        max_area = area
        mirror_rect = (x, y, ww, hh)

x0, y0, mw, mh = mirror_rect
mirror_roi = img[y0:y0+mh, x0:x0+mw]

# 2) Build dirt mask inside mirror ROI
gray = cv2.cvtColor(mirror_roi, cv2.COLOR_BGR2GRAY)
blur = cv2.GaussianBlur(gray, (BLUR_KSIZE, BLUR_KSIZE), 0)

thresh_light = cv2.adaptiveThreshold(
    blur, 255,
    cv2.ADAPTIVE_THRESH_MEAN_C,
    cv2.THRESH_BINARY_INV,
    THRESH_BLOCK_SIZE,
    THRESH_C
)
thresh_dark = cv2.adaptiveThreshold(
    255 - blur, 255,
    cv2.ADAPTIVE_THRESH_MEAN_C,
    cv2.THRESH_BINARY_INV,
    THRESH_BLOCK_SIZE,
    THRESH_C
)
thresh = cv2.bitwise_or(thresh_light, thresh_dark)

kernel_small = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (3, 3))
thresh = cv2.morphologyEx(thresh, cv2.MORPH_OPEN, kernel_small, iterations=1)
thresh = cv2.dilate(thresh, kernel_small, iterations=1)

# 3) Filter blobs by area and circularity, draw on original image
contours_dirt, _ = cv2.findContours(thresh, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

output = img.copy()
dirt_count = 0

for cnt in contours_dirt:
    area = cv2.contourArea(cnt)
    if area < MIN_DIRT_AREA or area > MAX_DIRT_AREA:
        continue

    perimeter = cv2.arcLength(cnt, True)
    if perimeter == 0:
        continue
    circularity = 4 * np.pi * area / (perimeter * perimeter)

    if circularity < MIN_CIRCULARITY:
        continue

    # print to console
    print(f"Spot {dirt_count}: area={area:.1f}, circularity={circularity:.3f}")

    x, y, ww, hh = cv2.boundingRect(cnt)
    cv2.rectangle(output, (x + x0, y + y0), (x + x0 + ww, y + y0 + hh), (0, 0, 255), 2)

    # optional: draw text near blob
    text = f"{int(area)} / {circularity:.2f}"
    cv2.putText(output, text, (x + x0, y + y0 - 5),
                cv2.FONT_HERSHEY_SIMPLEX, 0.4, (0, 255, 0), 1)

    dirt_count += 1


print("Detected dirt spots:", dirt_count)

cv2.imshow("mirror_roi_thresh", thresh)
cv2.imshow("dirt_detected", output)
cv2.imwrite(OUTPUT_PATH, output)
cv2.waitKey(0)
cv2.destroyAllWindows()
