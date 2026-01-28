from __future__ import annotations

import numpy as np
import pytest

from models.frame import Frame
from services.focus_assistant import FocusMetric
from services.white_balance import WhiteBalanceProcessor


def test_white_balance_processor_on_frame():
    processor = WhiteBalanceProcessor((0.5, 1.0, 1.5))
    data = np.ones((4, 4, 3), dtype=np.uint16) * 1000
    frame = Frame(data=data, timestamp_ns=0, frame_index=0)

    corrected = processor.process(frame)
    assert corrected.dtype == np.uint16
    assert corrected[0, 0, 0] == 500
    assert corrected[0, 0, 1] == 1000
    assert corrected[0, 0, 2] == 1500


def test_white_balance_processor_handles_non_rgb():
    processor = WhiteBalanceProcessor()
    data = np.ones((4, 4), dtype=np.uint16) * 1000
    corrected = processor.process(data)
    assert np.array_equal(corrected, data)


def test_focus_metric_distinguishes_sharpness():
    metric = FocusMetric()
    blurry = np.ones((64, 64, 3), dtype=np.uint16) * 1000

    sharp = blurry.copy()
    sharp[32:, :] += 1000

    frame_blurry = Frame(blurry, timestamp_ns=0, frame_index=0)
    frame_sharp = Frame(sharp, timestamp_ns=0, frame_index=1)

    score_blurry = metric.compute(frame_blurry)
    score_sharp = metric.compute(frame_sharp)

    assert score_sharp > score_blurry

