"""
Frame model containing image data and associated metadata.

Keeping frames as dataclasses provides a consistent structure for the
acquisition service, processing pipeline, and GUI while remaining easy
to extend with optional metadata.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, Tuple

import numpy as np


@dataclass
class Frame:
    """Single camera frame and its metadata."""

    data: np.ndarray
    timestamp_ns: int
    frame_index: int
    metadata: Dict[str, Any] = field(default_factory=dict)

    @property
    def shape(self) -> Tuple[int, ...]:
        """Return the numpy array shape."""
        return self.data.shape

    @property
    def height(self) -> int:
        """Image height in pixels."""
        return self.data.shape[0]

    @property
    def width(self) -> int:
        """Image width in pixels."""
        return self.data.shape[1]

    @property
    def channels(self) -> int:
        """Number of color channels."""
        if self.data.ndim == 3:
            return self.data.shape[2]
        return 1

