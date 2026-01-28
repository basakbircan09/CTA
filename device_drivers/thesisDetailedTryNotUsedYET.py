import cv2
import numpy as np

# ---------- 1. Load and resize ----------
img = cv2.imread(r"C:\Users\Monster\Desktop\tez\GC-Pics\ourTry\last\last14.jpg")
if img is None:
    raise FileNotFoundError("Image not found")

# resize whole image to make windows smaller (e.g. 40% of original)
scale_percent = 90
h0, w0 = img.shape[:2]
new_w = int(w0 * scale_percent / 100)
new_h = int(h0 * scale_percent / 100)
img = cv2.resize(img, (new_w, new_h), interpolation=cv2.INTER_LANCZOS4)
orig = img.copy()

# ---------- 2. Detect plate with Canny + contours ----------
gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
blur = cv2.GaussianBlur(gray, (5, 5), 0)

edges = cv2.Canny(blur, 45, 40)  # thresholds can be tuned

# dilate a bit so edges close
kernel = np.ones((3, 3), np.uint8)
edges_dil = cv2.dilate(edges, kernel, iterations=1)

contours, _ = cv2.findContours(
    edges_dil, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE
)

if len(contours) == 0:
    raise RuntimeError("No contours found")

# choose the largest contour as plate boundary
plate_cnt = max(contours, key=cv2.contourArea)

# rotated rectangle around that contour
rect = cv2.minAreaRect(plate_cnt)
box = cv2.boxPoints(rect)
box = box.astype(np.intp)

# draw it so we can see if it covers the whole plate
cv2.drawContours(orig, [box], 0, (0, 255, 0), 1)

# axis‑aligned crop of the rotated rectangle
x, y, w, h = cv2.boundingRect(plate_cnt)
plate_roi_color = img[y:y+h, x:x+w]


# --- NEW: detect spots from edges inside plate ROI ---

# 1) Canny on plate ROI
plate_gray = cv2.cvtColor(plate_roi_color, cv2.COLOR_BGR2GRAY)
plate_blur = cv2.GaussianBlur(plate_gray, (5, 5), 0)
plate_edges = cv2.Canny(plate_blur, 40, 50)

# 2) Dilate to close gaps in spot contours
kernel = np.ones((3, 3), np.uint8)
plate_edges_dil = cv2.dilate(plate_edges, kernel, iterations=1)

# 3) Find closed contours on edges
contours, _ = cv2.findContours(
    plate_edges_dil, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE
)

spots = []
for c in contours:
    area = cv2.contourArea(c)
    if area < 300 or area > 15000:   # tune based on your pixel size
        continue

    # circularity filter to keep roughly round blobs
    perim = cv2.arcLength(c, True)
    if perim == 0:
        continue
    circularity = 4 * np.pi * area / (perim * perim)
    if circularity < 0.01:
        continue

    spots.append(c)

print("Detected spots (edge contours):", len(spots))

plate_with_spots = plate_roi_color.copy()
cv2.drawContours(plate_with_spots, spots, -1, (0, 0, 255), 2)
out_dir = r"C:\Users\Monster\Desktop\tez\GC-Pics\ourTry\last"

cv2.imshow("plate_edges_dil", plate_edges_dil)
cv2.imshow("plate_with_spots_edges", plate_with_spots)
cv2.imwrite(out_dir + r"\thesisDetailedTryNotUsedYET.png", plate_with_spots)
cv2.waitKey(0)
cv2.destroyAllWindows()
#
#
# # ---------- 3. Prepare ROI for spot detection ----------
# plate_gray = cv2.cvtColor(plate_roi_color, cv2.COLOR_BGR2GRAY)
# plate_blur = cv2.GaussianBlur(plate_gray, (5, 5), 0)
#
#
# _, spot_bin = cv2.threshold(
#     plate_blur, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU
# )
#
# # ---------- 4. Blob detector ----------
# params = cv2.SimpleBlobDetector_Params()
#
# params.filterByColor = True
# params.blobColor = 255  # white blobs after INV
#
# params.filterByArea = True
# params.minArea = 5
# params.maxArea = 100000
#
# params.filterByCircularity = False
# #params.minCircularity = 0.1
#
# params.filterByConvexity = False
# params.filterByInertia = False
#
# detector = cv2.SimpleBlobDetector_create(params)
# keypoints = detector.detect(spot_bin)
#
# print("Detected spots:", len(keypoints))
#
# plate_with_blobs = cv2.drawKeypoints(
#     plate_roi_color, keypoints, np.array([]),
#     (0, 0, 255),
#     cv2.DRAW_MATCHES_FLAGS_DRAW_RICH_KEYPOINTS
# )
#
# # ---------- 5. Show in smaller windows ----------
# cv2.namedWindow("Original with plate", cv2.WINDOW_NORMAL)
# cv2.resizeWindow("Original with plate", 800, 450)
# cv2.imshow("Original with plate", orig)
#
# cv2.namedWindow("Edges", cv2.WINDOW_NORMAL)
# cv2.resizeWindow("Edges", 800, 450)
# cv2.imshow("Edges", edges_dil)
#
# cv2.namedWindow("Spot binary", cv2.WINDOW_NORMAL)
# cv2.resizeWindow("Spot binary", 400, 400)
# cv2.imshow("Spot binary", spot_bin)
#
# cv2.namedWindow("Plate with blobs", cv2.WINDOW_NORMAL)
# cv2.resizeWindow("Plate with blobs", 400, 400)
# cv2.imshow("Plate with blobs", plate_with_blobs)
#
# # # ---------- 6. Save intermediate images (temporary) ----------
# # out_dir = r"C:\Users\Monster\Desktop\tez\GC-Pics\ourTry"  # adjust if needed
# #
# # cv2.imwrite(out_dir + r"\orig_with_plate.png", orig)
# # cv2.imwrite(out_dir + r"\edges_dil.png", edges_dil)
# # cv2.imwrite(out_dir + r"\spot_bin.png", spot_bin)
# # cv2.imwrite(out_dir + r"\plate_with_blobs.png", plate_with_blobs)
#
#
# cv2.waitKey(0)
# cv2.destroyAllWindows()
