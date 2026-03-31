"""Image I/O and format-conversion utilities.

Keeps OpenCV imports out of main.py so the GUI layer contains no
computer-vision logic.
"""

import cv2
import numpy as np
from pathlib import Path


def load_image(path: str) -> np.ndarray | None:
    """Load a BGR image from disk.  Returns None if the path cannot be read."""
    return cv2.imread(str(path))


def save_image(path: str, img: np.ndarray) -> bool:
    """Save a BGR ndarray to disk.

    Creates parent directories as needed.
    Returns True on success, False on failure.
    """
    try:
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        return cv2.imwrite(str(path), img)
    except Exception:
        return False


def bgr_to_rgb(img: np.ndarray) -> np.ndarray:
    """Convert a BGR uint8 ndarray to RGB."""
    return cv2.cvtColor(img, cv2.COLOR_BGR2RGB)


def draw_spots_overlay(
    bgr: np.ndarray,
    reference: dict | None,
    spots: list,
    visited_count: int,
) -> np.ndarray:
    """Return a copy of *bgr* with reference and spot markers drawn on it.

    Parameters
    ----------
    bgr : ndarray
        Source BGR image (not modified).
    reference : dict | None
        Reference point dict with keys ``"x"``, ``"y"``.  Drawn in yellow.
    spots : list[dict]
        Spot dicts with keys ``"x"``, ``"y"``, ``"label"``.
    visited_count : int
        Spots at index < visited_count are considered already visited and
        drawn in green.  Unvisited spots are drawn in blue.
    """
    out = bgr.copy()
    r = 14   # circle radius in pixels
    font = cv2.FONT_HERSHEY_SIMPLEX

    if reference:
        cx, cy = int(reference["x"]), int(reference["y"])
        # Yellow in BGR = (0, 220, 220)
        cv2.circle(out, (cx, cy), r, (0, 220, 220), 2)
        cv2.circle(out, (cx, cy), 3, (0, 220, 220), -1)
        cv2.putText(out, "REF", (cx + r + 3, cy + 5), font, 0.55, (0, 220, 220), 2)

    for i, spot in enumerate(spots):
        cx, cy = int(spot["x"]), int(spot["y"])
        # Green (0,200,0) if visited, blue (220,80,0) if not (BGR)
        color = (0, 200, 0) if i < visited_count else (220, 80, 0)
        cv2.circle(out, (cx, cy), r, color, 2)
        cv2.circle(out, (cx, cy), 3, color, -1)
        cv2.putText(out, spot["label"], (cx + r + 3, cy + 5), font, 0.55, color, 2)

    return out
