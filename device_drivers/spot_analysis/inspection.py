# inspection.py

import numpy as np
import cv2
from .config import *


def inspect_spot_defects(gray, spot):

    mask = np.zeros(gray.shape, np.uint8)

    cv2.drawContours(mask,[spot["contour"]],-1,255,-1)

    vals = gray[mask==255]

    if vals.size < 80:

        return False, {
            "warning":"too_few_pixels",
            "n":int(vals.size)
        }

    med = np.median(vals)

    mad = np.median(np.abs(vals-med)) + 1e-6

    z = np.abs(vals-med)/(1.4826*mad)

    outlier_frac = np.mean(z>DEFAULT_MAD_K)

    t_dark = np.percentile(vals,DEFAULT_DARK_Q)
    t_bright = np.percentile(vals,DEFAULT_BRIGHT_Q)

    metrics = {
        "median":med,
        "mad":mad,
        "outlier_frac":outlier_frac,
        "t_dark":t_dark,
        "t_bright":t_bright,
        "reason":[]
    }

    if outlier_frac > DEFAULT_MAX_OUTLIER_FRAC:

        metrics["reason"].append("nonuniform")

    return len(metrics["reason"])>0, metrics