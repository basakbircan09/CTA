"""
Focus metric utilities to aid manual focus adjustment.

The metric is based on the variance of the Laplacian (when OpenCV is
available) or a numpy gradient fallback. Higher values indicate sharper
images with more high-frequency content.
"""

from __future__ import annotations

from typing import Union

import numpy as np

from models.frame import Frame

try:  # pragma: no cover - optional dependency for production
    import cv2  # type: ignore
except ImportError:  # pragma: no cover
    cv2 = None


ArrayLike = Union[np.ndarray, Frame]


class FocusMetric:
    """Compute focus sharpness scores."""

    def __init__(self) -> None:
        if cv2 is None:
            self._use_opencv = False
        else:
            self._use_opencv = True

    def compute(self, frame: ArrayLike) -> float:
        """Return a sharpness score (higher is sharper)."""
        data = frame.data if isinstance(frame, Frame) else frame
        gray = self._convert_to_gray(data)

        if self._use_opencv:
            lap = cv2.Laplacian(
                gray.astype(np.float64, copy=False),  # type: ignore[arg-type]
                cv2.CV_64F,
            )
            return float(lap.var())

        gy, gx = np.gradient(gray.astype(np.float32))
        magnitude = np.sqrt(gx ** 2 + gy ** 2)
        return float(np.mean(magnitude))

    @staticmethod
    def _convert_to_gray(data: np.ndarray) -> np.ndarray:
        if data.ndim == 2 or (data.ndim == 3 and data.shape[2] == 1):
            return data.astype(np.float32)
        if data.ndim == 3 and data.shape[2] >= 3:
            weights = np.array([0.299, 0.587, 0.114], dtype=np.float32)
            return np.tensordot(data.astype(np.float32), weights, axes=([2], [0]))
        raise ValueError("Unsupported frame shape for focus metric")
