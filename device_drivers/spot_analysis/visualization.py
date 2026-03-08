# visualization.py

import cv2
import numpy as np
from typing import List, Dict, Any


def _draw_label(
    img: np.ndarray,
    text: str,
    x: int,
    y: int,
    color: tuple,
) -> None:
    """Draw label text with a dark background rectangle for readability."""
    font      = cv2.FONT_HERSHEY_SIMPLEX
    scale     = 0.55
    thickness = 2
    (tw, th), baseline = cv2.getTextSize(text, font, scale, thickness)
    pad = 3
    # Dark background so text is readable on any image
    cv2.rectangle(
        img,
        (x - pad, y - th - pad),
        (x + tw + pad, y + baseline + pad),
        (20, 20, 20),
        -1,
    )
    cv2.putText(img, text, (x, y), font, scale, color, thickness, cv2.LINE_AA)


def draw_accept_reject_overlay(
    image: np.ndarray,
    spots: List[Dict[str, Any]],
) -> np.ndarray:
    """Draw accepted (blue) and rejected (red) spot contours with labels."""
    out = image.copy()
    for s in spots:
        bad   = s.get("is_bad", False)
        color = (0, 0, 255) if bad else (255, 0, 0)  # red=rejected, blue=accepted
        cv2.drawContours(out, [s["contour"]], -1, color, 2)
        cx, cy = s["center"]
        cv2.circle(out, (cx, cy), 4, color, -1)
        if "label" in s:
            _draw_label(out, s["label"], cx + 6, cy - 6, color)
    return out


def draw_rejected_candidates_overlay(
    image: np.ndarray,
    rejected_candidates: List[Dict[str, Any]],
) -> np.ndarray:
    """Draw detection-stage rejected candidates in yellow."""
    out = image.copy()
    for s in rejected_candidates:
        cv2.drawContours(out, [s["contour"]], -1, (0, 255, 255), 2)  # yellow
    return out