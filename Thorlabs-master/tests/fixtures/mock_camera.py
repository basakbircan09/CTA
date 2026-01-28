from __future__ import annotations

from dataclasses import dataclass
from typing import Tuple

import numpy as np


@dataclass
class MockThorlabsCamera:
    """
    Simplified stand-in for pylablib's ThorlabsTLCamera.

    Provides the minimal surface area required by the device adapter so
    unit tests can run without the actual hardware SDK.
    """

    serial: str
    width: int = 640
    height: int = 480
    sensor_type: str = "bayer"
    bit_depth: int = 12

    exposure_sec: float = 0.03
    gain_db: float = 0.0
    roi: Tuple[int, int, int, int, int, int] = (0, 640, 0, 480, 1, 1)

    def __post_init__(self) -> None:
        self._is_acquiring = False
        self._closed = False
        self._frame_counter = 0

    # ------------------------------------------------------------------
    # Camera API mirror
    # ------------------------------------------------------------------
    def get_device_info(self):
        return ("MockCam", "Mock Camera", self.serial, "FW1.0")

    def get_detector_size(self):
        return (self.width, self.height)

    def get_sensor_info(self):
        return {"type": self.sensor_type}

    def get_bit_depth(self):
        return self.bit_depth

    def get_exposure_range(self):
        return (0.001, 10.0)

    def get_exposure_limits(self):
        return self.get_exposure_range()

    def get_gain_range(self):
        return (0.0, 24.0)

    def get_gain_limits(self):
        return self.get_gain_range()

    def set_exposure(self, exposure_sec: float):
        self.exposure_sec = exposure_sec

    def set_gain(self, gain_db: float):
        self.gain_db = gain_db

    def set_roi(self, hstart: int, hend: int, vstart: int, vend: int, hbin: int, vbin: int):
        self.roi = (hstart, hend, vstart, vend, hbin, vbin)

    def get_roi(self):
        return self.roi

    def get_exposure(self):
        return self.exposure_sec

    def get_gain(self):
        return self.gain_db

    def start_acquisition(self):
        self._is_acquiring = True
        self._frame_counter = 0

    def stop_acquisition(self):
        self._is_acquiring = False

    def read_newest_image(self):
        if not self._is_acquiring:
            return None
        self._frame_counter += 1
        value = min(self._frame_counter, 65535)
        return np.full((self.height, self.width, 3), fill_value=value, dtype=np.uint16)

    def snap(self):
        self._frame_counter += 1
        value = max(1, min(self._frame_counter * 10, 65535))
        return np.full((self.height, self.width, 3), fill_value=value, dtype=np.uint16)

    def close(self):
        self._closed = True
        self._is_acquiring = False

    # ------------------------------------------------------------------
    # Helpers for assertions
    # ------------------------------------------------------------------
    @property
    def closed(self) -> bool:
        return self._closed
