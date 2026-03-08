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
