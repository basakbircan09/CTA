# config.py

# Detection filters
DEFAULT_MIN_SPOT_AREA = 450
DEFAULT_MAX_SPOT_AREA = 15000
DEFAULT_MIN_CIRCULARITY = 0.45
DEFAULT_MIN_SOLIDITY = 0.65

# Physical size filter (SFC opening criterion)
# mm_per_pixel is computed dynamically as plate_width_mm / crop_width_px.
# Spots whose diameter (from minEnclosingCircle) is below min_spot_diameter_mm
# are rejected before defect inspection.
DEFAULT_PLATE_WIDTH_MM = 50.0         # physical width of the sample plate (mm)
DEFAULT_MIN_SPOT_DIAMETER_MM = 1.5    # minimum acceptable spot diameter (mm)

# Preprocessing
DEFAULT_BG_BLUR_K = 81
DEFAULT_CLAHE_CLIP = 2.0
DEFAULT_CLAHE_TILE = (8, 8)

# Thresholding
DEFAULT_THRESH_BLOCKSIZE = 35
DEFAULT_THRESH_C = 2

# Morphology
DEFAULT_OPEN_KERNEL = 2
DEFAULT_CLOSE_KERNEL = 3

# Defect inspection
DEFAULT_ERODE_PX = 2
DEFAULT_MAD_K = 4.5
DEFAULT_MAX_OUTLIER_FRAC = 0.16

DEFAULT_DARK_Q = 10
DEFAULT_BRIGHT_Q = 95
DEFAULT_DEFECT_AREA_FRAC = 0.03
DEFAULT_MIN_DEFECT_AREA_PX = 35
