# config.py

# Detection filters
DEFAULT_MIN_SPOT_AREA = 450
DEFAULT_MAX_SPOT_AREA = 15000
DEFAULT_MIN_CIRCULARITY = 0.45
DEFAULT_MIN_SOLIDITY = 0.65

# Physical size filter (SFC opening criterion)
# Spots whose diameter (from minEnclosingCircle) is below this threshold are
# rejected before defect inspection.
DEFAULT_MM_PER_PIXEL = 0.094          # mm per pixel at 20 cm camera distance
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
DEFAULT_MAD_K = 4.5
DEFAULT_MAX_OUTLIER_FRAC = 0.16

DEFAULT_DARK_Q = 10
DEFAULT_BRIGHT_Q = 95
DEFAULT_DEFECT_AREA_FRAC = 0.03
DEFAULT_MIN_DEFECT_AREA_PX = 35