"""
Data models for the vision module.
"""

from dataclasses import dataclass, field
from typing import List, Optional, Tuple
from enum import Enum, auto


class DetectionMode(Enum):
    """Sample detection mode."""
    CIRCLES = auto()      # Circular wells (96-well plates, droplets)
    RECTANGLES = auto()   # Rectangular samples (electrodes, chips)
    AUTO = auto()         # Try both, use best result


@dataclass
class DetectionParams:
    """Parameters for sample detection algorithm.

    Attributes:
        mode: Detection mode (circles, rectangles, or auto)
        min_radius_px: Minimum sample radius in pixels (circles mode)
        max_radius_px: Maximum sample radius in pixels (circles mode)
        min_area_px: Minimum sample area in pixels (rectangles mode)
        max_area_px: Maximum sample area in pixels (rectangles mode)
        min_confidence: Minimum confidence threshold (0.0 - 1.0)
        blur_kernel_size: Gaussian blur kernel size for noise reduction
        canny_threshold_low: Canny edge detection low threshold
        canny_threshold_high: Canny edge detection high threshold
        hough_param1: HoughCircles param1 (edge detection threshold)
        hough_param2: HoughCircles param2 (accumulator threshold)
        min_distance_px: Minimum distance between detected samples
    """
    mode: DetectionMode = DetectionMode.CIRCLES

    # Circle detection params
    min_radius_px: int = 10
    max_radius_px: int = 150

    # Rectangle detection params
    min_area_px: int = 30
    max_area_px: int = 500000

    # Common params
    min_confidence: float = 0.1
    blur_kernel_size: int = 7
    canny_threshold_low: int = 40
    canny_threshold_high: int = 40
    hough_param1: int = 80
    hough_param2: int = 30
    min_distance_px: int = 10


@dataclass
class DetectedSample:
    """A detected sample position in pixel coordinates.

    Attributes:
        pixel_x: X coordinate in pixels (from image left)
        pixel_y: Y coordinate in pixels (from image top)
        radius: Detected radius in pixels (for circles)
        width: Detected width in pixels (for rectangles)
        height: Detected height in pixels (for rectangles)
        confidence: Detection confidence (0.0 - 1.0)
        label: Auto-generated label (e.g., "A1", "S01")
    """
    pixel_x: int
    pixel_y: int
    radius: Optional[int] = None
    width: Optional[int] = None
    height: Optional[int] = None
    confidence: float = 1.0
    label: Optional[str] = None

    @property
    def center(self) -> Tuple[int, int]:
        """Return (x, y) center coordinates."""
        return (self.pixel_x, self.pixel_y)


@dataclass
class CalibrationData:
    """Camera-to-stage coordinate transformation parameters.

    The coordinate system assumes:
    - Camera is mounted perpendicular to stage, looking down at Z+ direction
    - Image origin (0, 0) is top-left corner
    - Stage origin is defined by PI XYZ home position

    Attributes:
        mm_per_pixel_x: Scale factor for X axis (mm per pixel)
        mm_per_pixel_y: Scale factor for Y axis (mm per pixel)
        origin_stage_x_mm: Stage X position when camera sees image center
        origin_stage_y_mm: Stage Y position when camera sees image center
        fixed_z_mm: Fixed Z height for all detected samples
        image_width_px: Expected image width in pixels
        image_height_px: Expected image height in pixels
        rotation_deg: Rotation offset between camera and stage axes (usually 0 or 180)
        flip_x: Whether to flip X axis
        flip_y: Whether to flip Y axis
    """
    mm_per_pixel_x: float
    mm_per_pixel_y: float
    origin_stage_x_mm: float
    origin_stage_y_mm: float
    fixed_z_mm: float
    image_width_px: int = 1440
    image_height_px: int = 1080
    rotation_deg: float = 0.0
    flip_x: bool = False
    flip_y: bool = False

    # Metadata
    calibration_date: Optional[str] = None
    notes: Optional[str] = None


@dataclass
class ScanResult:
    """Result of a plate scan operation.

    Attributes:
        image_path: Path to the captured image
        detections: List of detected samples in pixel coords
        positions: List of converted stage positions
        calibration: Calibration data used
        params: Detection parameters used
        warnings: Any warnings during detection
    """
    image_path: str
    detections: List[DetectedSample]
    positions: List["ArrayPosition"]  # Forward ref to avoid circular import
    calibration: CalibrationData
    params: DetectionParams
    warnings: List[str] = field(default_factory=list)