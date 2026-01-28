"""
Frame persistence utilities (PNG/TIFF).
"""

from __future__ import annotations

from pathlib import Path
from typing import Optional

import numpy as np
from PIL import Image

try:  # pragma: no cover - optional dependency
    import tifffile  # type: ignore
except ImportError:  # pragma: no cover
    tifffile = None

from models.frame import Frame


class FrameSaver:
    """Persist frames to disk in common formats."""

    def __init__(self, output_dir: Path) -> None:
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)

    def save_png(self, frame: Frame, filename: Optional[str] = None, autoscale: bool = True) -> Path:
        path = self._resolve_path(filename, suffix=".png")
        image_8bit = self._to_uint8(frame.data, autoscale=autoscale)
        img = Image.fromarray(image_8bit)
        img.save(path)
        return path

    def save_tiff(self, frame: Frame, filename: Optional[str] = None) -> Path:
        if tifffile is None:
            raise RuntimeError("tifffile is required to save TIFF images.")
        path = self._resolve_path(filename, suffix=".tiff")
        metadata = dict(frame.metadata)
        metadata.setdefault("frame_index", frame.frame_index)
        metadata.setdefault("timestamp_ns", frame.timestamp_ns)
        tifffile.imwrite(path, frame.data, metadata=metadata)
        return path

    def _resolve_path(self, filename: Optional[str], suffix: str) -> Path:
        if filename is None:
            from datetime import datetime

            stamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
            name = f"frame_{stamp}{suffix}"
        else:
            name = filename if filename.lower().endswith(suffix) else f"{filename}{suffix}"
        return self.output_dir / name

    @staticmethod
    def _to_uint8(data: np.ndarray, autoscale: bool = True) -> np.ndarray:
        if data.dtype == np.uint8:
            return data
        if np.issubdtype(data.dtype, np.integer):
            float_data = data.astype(np.float32)
            if autoscale:
                min_val = float(float_data.min())
                max_val = float(float_data.max())
                if max_val <= min_val:
                    return np.zeros_like(data, dtype=np.uint8)
                scaled = (float_data - min_val) / (max_val - min_val)
            else:
                info = np.iinfo(data.dtype)
                scaled = (float_data - info.min) / max(info.max - info.min, 1)
            return (scaled * 255).clip(0, 255).astype(np.uint8)
        scaled = np.clip(data, 0.0, 1.0)
        return (scaled * 255).astype(np.uint8)
