# visualization.py

import cv2
import numpy as np
from typing import List, Dict, Any


def draw_accept_reject_overlay(
    image: np.ndarray,
    spots: List[Dict[str, Any]],
) -> np.ndarray:
    """Draw accepted (blue) and rejected (red) spot contours with labels."""
    out = image.copy()
    for s in spots:
        bad = s.get("is_bad", False)
        color = (0, 0, 255) if bad else (255, 0, 0)  # red=rejected, blue=accepted
        cv2.drawContours(out, [s["contour"]], -1, color, 2)
        cx, cy = s["center"]
        cv2.circle(out, (cx, cy), 3, (0, 0, 255), -1)
        if "label" in s:
            cv2.putText(
                out, s["label"], (cx + 5, cy - 5),
                cv2.FONT_HERSHEY_SIMPLEX, 0.5, color, 1,
            )
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