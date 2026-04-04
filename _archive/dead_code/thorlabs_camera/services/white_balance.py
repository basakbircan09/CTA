"""
White balance processing helpers.

The processor operates on numpy arrays or Frame objects, applying simple
per-channel gain correction while preserving the underlying dtype.
"""

from __future__ import annotations

from typing import Iterable, Tuple, Union

import numpy as np

from models.frame import Frame

ArrayLike = Union[np.ndarray, Frame]


class WhiteBalanceProcessor:
    """Apply RGB gain adjustments to camera frames."""

    def __init__(self, gains: Tuple[float, float, float] = (1.0, 1.0, 1.0)) -> None:
        self._gains = np.array(gains, dtype=np.float32)

    @property
    def gains(self) -> Tuple[float, float, float]:
        return tuple(float(x) for x in self._gains)

    def set_gains(self, red: float, green: float, blue: float) -> None:
        self._gains = np.array((red, green, blue), dtype=np.float32)

    def process(self, frame: ArrayLike) -> np.ndarray:
        """Return a white-balanced numpy array."""
        data = frame.data if isinstance(frame, Frame) else frame
        if data.ndim < 3 or data.shape[2] != 3:
            return np.array(data, copy=True)

        gains = self._gains.reshape((1, 1, 3))
        float_data = data.astype(np.float32) * gains

        if np.issubdtype(data.dtype, np.integer):
            dtype_info = np.iinfo(data.dtype)
            float_data = np.clip(float_data, dtype_info.min, dtype_info.max)
            return float_data.astype(data.dtype)

        return float_data

