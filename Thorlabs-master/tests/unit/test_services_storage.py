from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest

from models.frame import Frame
from services.storage import FrameSaver


def test_frame_saver_creates_png(tmp_path: Path):
    saver = FrameSaver(tmp_path)
    data = (np.random.rand(10, 10, 3) * 65535).astype(np.uint16)
    frame = Frame(data=data, timestamp_ns=123, frame_index=1)

    path = saver.save_png(frame, filename="test_image")
    assert path.exists()
    assert path.suffix == ".png"


def test_frame_saver_creates_tiff(tmp_path: Path):
    pytest.importorskip("tifffile")
    saver = FrameSaver(tmp_path)
    data = (np.random.rand(10, 10, 3) * 65535).astype(np.uint16)
    frame = Frame(data=data, timestamp_ns=456, frame_index=2)

    path = saver.save_tiff(frame, filename="test_image")
    assert path.exists()
    assert path.suffix in (".tiff", ".tif")

