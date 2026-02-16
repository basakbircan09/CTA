"""
Dataclasses describing camera configuration state and capabilities.

These models are intentionally lightweight to make serialization,
validation, and testing straightforward. They sit between the GUI/service
layers and the device adapter, keeping pylablib-specific tuples confined
to the adapter implementation.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional, Tuple, Dict, Any


@dataclass(frozen=True)
class ROI:
    """Region of interest on the sensor."""

    x: int
    y: int
    width: int
    height: int
    bin_x: int = 1
    bin_y: int = 1

    def to_pylablib(self) -> Tuple[int, int, int, int, int, int]:
        """
        Convert to pylablib's ROI tuple:
        (hstart, hend, vstart, vend, hbin, vbin)
        """
        return (
            self.x,
            self.x + self.width,
            self.y,
            self.y + self.height,
            self.bin_x,
            self.bin_y,
        )

    @staticmethod
    def from_pylablib(roi_tuple: Tuple[int, int, int, int, int, int]) -> "ROI":
        """Create an ROI instance from pylablib's tuple representation."""
        hstart, hend, vstart, vend, hbin, vbin = roi_tuple
        return ROI(
            x=hstart,
            y=vstart,
            width=hend - hstart,
            height=vend - vstart,
            bin_x=hbin,
            bin_y=vbin,
        )

    @staticmethod
    def full_frame(width: int, height: int) -> "ROI":
        """Convenience constructor covering the full sensor area."""
        return ROI(x=0, y=0, width=width, height=height)


@dataclass
class CameraSettings:
    """Collection of camera settings that can change at runtime."""

    exposure_sec: float
    gain_db: float
    roi: Optional[ROI] = None
    white_balance_rgb: Tuple[float, float, float] = (1.0, 1.0, 1.0)

    def to_dict(self) -> Dict[str, Any]:
        """Serialize settings to a plain dictionary."""
        roi_dict = (
            {
                "x": self.roi.x,
                "y": self.roi.y,
                "width": self.roi.width,
                "height": self.roi.height,
                "bin_x": self.roi.bin_x,
                "bin_y": self.roi.bin_y,
            }
            if self.roi
            else None
        )
        return {
            "exposure_sec": self.exposure_sec,
            "gain_db": self.gain_db,
            "roi": roi_dict,
            "white_balance_rgb": list(self.white_balance_rgb),
        }

    @staticmethod
    def from_dict(data: Dict[str, Any]) -> "CameraSettings":
        """Deserialize settings from a dictionary."""
        roi_data = data.get("roi")
        roi = ROI(**roi_data) if roi_data else None
        white_balance = tuple(data.get("white_balance_rgb", (1.0, 1.0, 1.0)))
        return CameraSettings(
            exposure_sec=data["exposure_sec"],
            gain_db=data["gain_db"],
            roi=roi,
            white_balance_rgb=white_balance,  # type: ignore[arg-type]
        )


@dataclass(frozen=True)
class CameraCapabilities:
    """Static camera capabilities reported at connection time."""

    model: str
    serial: str
    firmware: str
    sensor_width: int
    sensor_height: int
    sensor_type: str
    bit_depth: int
    exposure_range_sec: Tuple[float, float]
    gain_range_db: Tuple[float, float]

