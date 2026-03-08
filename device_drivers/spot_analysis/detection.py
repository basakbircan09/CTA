# detection.py

import cv2
import numpy as np
from typing import Dict, Any, List, Tuple

from .config import *


def preprocess_for_detection(bgr, debug=None):

    gray = cv2.cvtColor(bgr, cv2.COLOR_BGR2GRAY)

    k = DEFAULT_BG_BLUR_K if DEFAULT_BG_BLUR_K % 2 else DEFAULT_BG_BLUR_K + 1
    bg = cv2.GaussianBlur(gray, (k, k), 0)

    bg = np.clip(bg, 1, 255).astype(np.uint8)

    norm = cv2.divide(gray, bg, scale=255)

    clahe = cv2.createCLAHE(
        clipLimit=DEFAULT_CLAHE_CLIP,
        tileGridSize=DEFAULT_CLAHE_TILE
    )

    norm = clahe.apply(norm)

    if debug is not None:
        debug["gray_raw"] = gray
        debug["bg"] = bg
        debug["gray_norm"] = norm

    return norm


def detect_spots(image, debug=None):

    pdbg = {}
    norm = preprocess_for_detection(image, debug=pdbg)

    blur = cv2.GaussianBlur(norm, (5, 5), 0)

    thresh = cv2.adaptiveThreshold(
        blur,
        255,
        cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
        cv2.THRESH_BINARY_INV,
        DEFAULT_THRESH_BLOCKSIZE,
        DEFAULT_THRESH_C
    )

    opened = cv2.morphologyEx(
        thresh,
        cv2.MORPH_OPEN,
        np.ones((DEFAULT_OPEN_KERNEL, DEFAULT_OPEN_KERNEL), np.uint8)
    )

    closed = cv2.morphologyEx(
        opened,
        cv2.MORPH_CLOSE,
        np.ones((DEFAULT_CLOSE_KERNEL, DEFAULT_CLOSE_KERNEL), np.uint8)
    )

    if debug is not None:
        debug.update(pdbg)
        debug["thresh_bw"] = thresh
        debug["opened"] = opened
        debug["closed"] = closed

    contours, _ = cv2.findContours(
        closed,
        cv2.RETR_EXTERNAL,
        cv2.CHAIN_APPROX_SIMPLE
    )

    spots = []
    rejected = []

    for c in contours:

        area = cv2.contourArea(c)
        peri = cv2.arcLength(c, True)

        circ = 0 if peri == 0 else 4*np.pi*area/(peri**2)

        hull = cv2.convexHull(c)
        hull_area = cv2.contourArea(hull)

        solidity = 0 if hull_area == 0 else area/hull_area

        reason = None

        if not (DEFAULT_MIN_SPOT_AREA <= area <= DEFAULT_MAX_SPOT_AREA):
            reason = "area"

        elif circ < DEFAULT_MIN_CIRCULARITY:
            reason = "circularity"

        elif solidity < DEFAULT_MIN_SOLIDITY:
            reason = "solidity"

        if reason:

            rejected.append({
                "contour": c,
                "reason": reason,
                "area": area,
                "circularity": circ,
                "solidity": solidity
            })

            continue

        M = cv2.moments(c)

        if M["m00"] == 0:
            continue

        cx = int(M["m10"]/M["m00"])
        cy = int(M["m01"]/M["m00"])

        spots.append({
            "contour": c,
            "center": (cx,cy),
            "area": area,
            "circularity": circ,
            "solidity": solidity
        })

    return spots, rejected, pdbg