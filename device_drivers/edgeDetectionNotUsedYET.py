import cv2
import numpy as np

# 1. Load image
img = cv2.imread(r"C:\Users\Monster\Desktop\tez\GC-Pics\ourTry\last\last14.jpg")          # <-- put your filename here
scale_percent = 15

width  = int(img.shape[1] * scale_percent / 100)
height = int(img.shape[0] * scale_percent / 100)
dim = (width, height)

img_small = cv2.resize(img, dim, interpolation=cv2.INTER_AREA)

orig = img_small.copy()

# 2. Pre‑processing
gray = cv2.cvtColor(img_small, cv2.COLOR_BGR2GRAY)
blur = cv2.GaussianBlur(gray, (5, 5), 0)

# Try automatic threshold (Otsu) – works well for single object on background
_, thresh = cv2.threshold(
    blur, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU
)

# If the plate comes out white and background black, keep it.
# If it is inverted, flip it:
plate_is_dark = np.mean(gray) < 128    # quick heuristic, you can comment this out
if plate_is_dark:
    thresh = cv2.bitwise_not(thresh)

# 3. Find contours
contours, hierarchy = cv2.findContours(
    thresh, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE
)

if len(contours) == 0:
    print("No contours found")
else:
    # 4. Take the largest contour (assumed to be the plate)
    cnt = max(contours, key=cv2.contourArea)

    # Optional: approximate to a polygon and ensure it's roughly rectangular
    epsilon = 0.02 * cv2.arcLength(cnt, True)
    approx = cv2.approxPolyDP(cnt, epsilon, True)

    # 5. Draw bounding box
    # a) axis‑aligned rectangle:
    x, y, w, h = cv2.boundingRect(cnt)
    cv2.rectangle(orig, (x, y), (x + w, y + h), (0, 255, 0), 3)

    # b) or rotated rectangle (better if plate is tilted):
    rect = cv2.minAreaRect(cnt)
    box = cv2.boxPoints(rect)
    box = box.astype(np.intp)
    cv2.drawContours(orig, [box], 0, (0, 0, 255), 3)

    print("Bounding box (x, y, w, h):", x, y, w, h)

if len(contours) == 0:
    print("No contours found")
else:
    cnt = max(contours, key=cv2.contourArea)

    if cv2.contourArea(cnt) < 10:  # arbitrary small area filter
        print("Largest contour too small")
    else:
        rect = cv2.minAreaRect(cnt)
        box = cv2.boxPoints(rect)
        box = box.astype(np.intp)

        if box.shape[0] > 0:
            cv2.drawContours(orig, [box], 0, (0, 0, 255), 3)
        else:
            print("Box points are empty")

# 6. Show results
cv2.imshow("gray", gray)
cv2.imshow("thresh", thresh)
cv2.imshow("plate_detection", orig)
cv2.waitKey(0)
cv2.destroyAllWindows()
