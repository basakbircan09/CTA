"""
generate_thesis_figures.py

Generates thesis figures for the spot detection preprocessing and
segmentation sections. Loads a single plate image and produces:

  fig_preprocessing_pipeline.png  — 4-panel preprocessing walkthrough
  fig_segmentation_pipeline.png   — 4-panel segmentation walkthrough
  fig_contours_overlay.png        — all detected external contours on colour image

All outputs are written to the same directory as the input image.
"""

import sys
from pathlib import Path

import cv2
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------

IMAGE_PATH = Path(
    r"C:\Users\Monster\Desktop\tez\writingPart\writing04.08"
    r"\ThesisImagesNotesSpotDetection\spotDetectDetails\01_original.png"
)
OUTPUT_DIR = IMAGE_PATH.parent

# ---------------------------------------------------------------------------
# Load image
# ---------------------------------------------------------------------------

img_bgr = cv2.imread(str(IMAGE_PATH))
if img_bgr is None:
    print(f"ERROR: Cannot load image at:\n  {IMAGE_PATH}", file=sys.stderr)
    sys.exit(1)

print(f"Loaded: {IMAGE_PATH.name}  ({img_bgr.shape[1]}×{img_bgr.shape[0]} px)")

# Convert to grayscale once — all processing operates on grayscale
gray = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2GRAY)

# ---------------------------------------------------------------------------
# Preprocessing pipeline
# ---------------------------------------------------------------------------

# Step 1 — original (grayscale view)
step1_original = gray.copy()

# Step 2 — background normalisation (divide by large-kernel Gaussian blur)
k = 81  # must be odd
bg = cv2.GaussianBlur(gray, (k, k), 0)
bg = np.clip(bg, 1, 255).astype(np.uint8)
step2_bg_norm = cv2.divide(gray, bg, scale=255)

# Step 3 — CLAHE on the normalised image
clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
step3_clahe = clahe.apply(step2_bg_norm)

# Step 4 — 5×5 Gaussian blur (input to thresholding)
step4_blur = cv2.GaussianBlur(step3_clahe, (5, 5), 0)

# ---------------------------------------------------------------------------
# Segmentation pipeline  (continues from step 4)
# ---------------------------------------------------------------------------

# Step 5 — adaptive Gaussian threshold
blocksize = 35   # must be odd
thresh_c  = 2
step5_thresh = cv2.adaptiveThreshold(
    step4_blur, 255,
    cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
    cv2.THRESH_BINARY_INV,
    blocksize,
    thresh_c,
)

# Step 6 — morphological opening (2×2 kernel)
step6_opened = cv2.morphologyEx(
    step5_thresh,
    cv2.MORPH_OPEN,
    np.ones((2, 2), np.uint8),
)

# Step 7 — morphological closing (3×3 kernel)
step7_closed = cv2.morphologyEx(
    step6_opened,
    cv2.MORPH_CLOSE,
    np.ones((3, 3), np.uint8),
)

# ---------------------------------------------------------------------------
# Contour extraction
# ---------------------------------------------------------------------------

contours, _ = cv2.findContours(
    step7_closed, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE
)

# Draw all contours on a colour copy of the original
contour_overlay = img_bgr.copy()
cv2.drawContours(contour_overlay, contours, -1, (0, 255, 0), thickness=1)
# Convert BGR → RGB for matplotlib
contour_overlay_rgb = cv2.cvtColor(contour_overlay, cv2.COLOR_BGR2RGB)

print(f"Total external contours found: {len(contours)}")

# ---------------------------------------------------------------------------
# Helper — common subplot styling
# ---------------------------------------------------------------------------

def _ax(ax, image, title, cmap="gray"):
    ax.imshow(image, cmap=cmap, vmin=0, vmax=255)
    ax.set_title(title, fontsize=13, pad=6)
    ax.axis("off")

# ---------------------------------------------------------------------------
# Figure 1 — Preprocessing pipeline
# ---------------------------------------------------------------------------

fig1, axes1 = plt.subplots(1, 4, figsize=(18, 5))
fig1.suptitle("Preprocessing Pipeline", fontsize=15, fontweight="bold", y=1.01)

_ax(axes1[0], step1_original,  "Original")
_ax(axes1[1], step2_bg_norm,   "Background Normalized")
_ax(axes1[2], step3_clahe,     "After CLAHE")
_ax(axes1[3], step4_blur,      "After Gaussian Blur")

fig1.tight_layout()
out1 = OUTPUT_DIR / "fig_preprocessing_pipeline.png"
fig1.savefig(str(out1), dpi=300, bbox_inches="tight")
plt.close(fig1)
print(f"Saved → {out1}")

# ---------------------------------------------------------------------------
# Figure 2 — Segmentation pipeline
# ---------------------------------------------------------------------------

fig2, axes2 = plt.subplots(1, 4, figsize=(18, 5))
fig2.suptitle("Segmentation Pipeline", fontsize=15, fontweight="bold", y=1.01)

_ax(axes2[0], step4_blur,     "Preprocessed Input")
_ax(axes2[1], step5_thresh,   "Adaptive Threshold")
_ax(axes2[2], step6_opened,   "After Opening")
_ax(axes2[3], step7_closed,   "After Closing")

fig2.tight_layout()
out2 = OUTPUT_DIR / "fig_segmentation_pipeline.png"
fig2.savefig(str(out2), dpi=300, bbox_inches="tight")
plt.close(fig2)
print(f"Saved → {out2}")

# ---------------------------------------------------------------------------
# Figure 3 — Detected contours overlay
# ---------------------------------------------------------------------------

fig3, ax3 = plt.subplots(1, 1, figsize=(8, 6))
fig3.suptitle("Detected Candidate Contours", fontsize=15, fontweight="bold")

ax3.imshow(contour_overlay_rgb)
ax3.axis("off")

fig3.tight_layout()
out3 = OUTPUT_DIR / "fig_contours_overlay.png"
fig3.savefig(str(out3), dpi=300, bbox_inches="tight")
plt.close(fig3)
print(f"Saved → {out3}")

print("\nDone. All 3 figures written.")
