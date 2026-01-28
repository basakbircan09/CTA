# """
# Data models for the module AFTER THESE COMMENTED PART called "models.py".
# """
#
# from dataclasses import dataclass, field
# from typing import List, Optional, Tuple
# from enum import Enum, auto
#
#
# class DetectionMode(Enum):
#     """Sample detection mode."""
#     CIRCLES = auto()      # Circular wells (96-well plates, droplets)
#     RECTANGLES = auto()   # Rectangular samples (electrodes, chips)
#     AUTO = auto()         # Try both, use best result
#
#
# @dataclass
# class DetectionParams:
#     """Parameters for sample detection algorithm.
#
#     Attributes:
#         mode: Detection mode (circles, rectangles, or auto)
#         min_radius_px: Minimum sample radius in pixels (circles mode)
#         max_radius_px: Maximum sample radius in pixels (circles mode)
#         min_area_px: Minimum sample area in pixels (rectangles mode)
#         max_area_px: Maximum sample area in pixels (rectangles mode)
#         min_confidence: Minimum confidence threshold (0.0 - 1.0)
#         blur_kernel_size: Gaussian blur kernel size for noise reduction
#         canny_threshold_low: Canny edge detection low threshold
#         canny_threshold_high: Canny edge detection high threshold
#         hough_param1: HoughCircles param1 (edge detection threshold)
#         hough_param2: HoughCircles param2 (accumulator threshold)
#         min_distance_px: Minimum distance between detected samples
#     """
#     mode: DetectionMode = DetectionMode.CIRCLES
#
#     # Circle detection params
#     min_radius_px: int = 10
#     max_radius_px: int = 150
#
#     # Rectangle detection params
#     min_area_px: int = 30
#     max_area_px: int = 500000
#
#     # Common params
#     min_confidence: float = 0.1
#     blur_kernel_size: int = 7
#     canny_threshold_low: int = 40
#     canny_threshold_high: int = 40
#     hough_param1: int = 80
#     hough_param2: int = 30
#     min_distance_px: int = 10
#
#
# @dataclass
# class DetectedSample:
#     """A detected sample position in pixel coordinates.
#
#     Attributes:
#         pixel_x: X coordinate in pixels (from image left)
#         pixel_y: Y coordinate in pixels (from image top)
#         radius: Detected radius in pixels (for circles)
#         width: Detected width in pixels (for rectangles)
#         height: Detected height in pixels (for rectangles)
#         confidence: Detection confidence (0.0 - 1.0)
#         label: Auto-generated label (e.g., "A1", "S01")
#     """
#     pixel_x: int
#     pixel_y: int
#     radius: Optional[int] = None
#     width: Optional[int] = None
#     height: Optional[int] = None
#     confidence: float = 1.0
#     label: Optional[str] = None
#
#     @property
#     def center(self) -> Tuple[int, int]:
#         """Return (x, y) center coordinates."""
#         return (self.pixel_x, self.pixel_y)
#
#
# @dataclass
# class CalibrationData:
#     """Camera-to-stage coordinate transformation parameters.
#
#     The coordinate system assumes:
#     - Camera is mounted perpendicular to stage, looking down at Z+ direction
#     - Image origin (0, 0) is top-left corner
#     - Stage origin is defined by PI XYZ home position
#
#     Attributes:
#         mm_per_pixel_x: Scale factor for X axis (mm per pixel)
#         mm_per_pixel_y: Scale factor for Y axis (mm per pixel)
#         origin_stage_x_mm: Stage X position when camera sees image center
#         origin_stage_y_mm: Stage Y position when camera sees image center
#         fixed_z_mm: Fixed Z height for all detected samples
#         image_width_px: Expected image width in pixels
#         image_height_px: Expected image height in pixels
#         rotation_deg: Rotation offset between camera and stage axes (usually 0 or 180)
#         flip_x: Whether to flip X axis
#         flip_y: Whether to flip Y axis
#     """
#     mm_per_pixel_x: float
#     mm_per_pixel_y: float
#     origin_stage_x_mm: float
#     origin_stage_y_mm: float
#     fixed_z_mm: float
#     image_width_px: int = 1440
#     image_height_px: int = 1080
#     rotation_deg: float = 0.0
#     flip_x: bool = False
#     flip_y: bool = False
#
#     # Metadata
#     calibration_date: Optional[str] = None
#     notes: Optional[str] = None
#
#
# @dataclass
# class ScanResult:
#     """Result of a plate scan operation.
#
#     Attributes:
#         image_path: Path to the captured image
#         detections: List of detected samples in pixel coords
#         positions: List of converted stage positions
#         calibration: Calibration data used
#         params: Detection parameters used
#         warnings: Any warnings during detection
#     """
#     image_path: str
#     detections: List[DetectedSample]
#     positions: List["ArrayPosition"]  # Forward ref to avoid circular import
#     calibration: CalibrationData
#     params: DetectionParams
#     warnings: List[str] = field(default_factory=list)

import logging
import sys
from pathlib import Path
from typing import List, Optional, Tuple

import numpy as np
from models import DetectedSample, DetectionParams, DetectionMode

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

try:
    import cv2
except ImportError:
    print("ERROR: OpenCV required. Install: pip install opencv-python")
    sys.exit(1)

IMAGE_PATH = r"C:\Users\Monster\Desktop\tez\GC-Pics\ourTry\last\last14.jpg"
OUTPUT_PATH = r"C:\Users\Monster\Desktop\tez\GC-Pics\ourTry\last\last14_sampleDetector.jpg"


class SampleDetector:
    def __init__(self, params: Optional[DetectionParams] = None):
        self.params = params or DetectionParams()

    def find_samples(self, image_path: str, params: Optional[DetectionParams] = None) -> List[DetectedSample]:
        path = Path(image_path)
        if not path.exists():
            raise FileNotFoundError(f"Image not found: {image_path}")

        image = cv2.imread(str(path))
        if image is None:
            raise ValueError(f"Failed to load image: {image_path}")

        return self.find_samples_in_array(image, params), image

    def find_samples_in_array(self, image: np.ndarray, params: Optional[DetectionParams] = None) -> List[DetectedSample]:
        p = params or self.params
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY) if len(image.shape) == 3 else image
        blurred = cv2.GaussianBlur(gray, (p.blur_kernel_size, p.blur_kernel_size), 0)

        if p.mode == DetectionMode.CIRCLES:
            detections = self._find_circles(blurred, p)
        elif p.mode == DetectionMode.RECTANGLES:
            detections = self._find_rectangles(blurred, p)
        else:
            circles = self._find_circles(blurred, p)
            rectangles = self._find_rectangles(blurred, p)
            detections = circles if len(circles) >= len(rectangles) else rectangles

        detections = self._filter_by_distance(detections, p.min_distance_px)
        detections = [d for d in detections if d.confidence >= p.min_confidence]
        detections = self._sort_grid_order(detections)
        detections = self._assign_labels(detections)
        logger.info(f"Detected {len(detections)} samples")
        return detections

    def _find_circles(self, gray: np.ndarray, params: DetectionParams) -> List[DetectedSample]:
        circles = cv2.HoughCircles(
            gray,
            cv2.HOUGH_GRADIENT,
            dp=1,
            minDist=params.min_distance_px,
            param1=params.hough_param1,
            param2=params.hough_param2,
            minRadius=params.min_radius_px,
            maxRadius=params.max_radius_px,
        )
        if circles is None:
            return []
        detections: List[DetectedSample] = []
        circles = np.uint16(np.around(circles))
        for circle in circles[0, :]:
            x, y, r = circle
            confidence = min(1.0, params.hough_param2 / 50.0)
            detections.append(
                DetectedSample(pixel_x=int(x), pixel_y=int(y), radius=int(r), confidence=confidence)
            )
        return detections

    def _find_rectangles(self, gray: np.ndarray, params: DetectionParams) -> List[DetectedSample]:
        edges = cv2.Canny(gray, params.canny_threshold_low, params.canny_threshold_high)
        contours, _ = cv2.findContours(edges, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        detections: List[DetectedSample] = []
        for contour in contours:
            area = cv2.contourArea(contour)
            if area < params.min_area_px or area > params.max_area_px:
                continue
            x, y, w, h = cv2.boundingRect(contour)
            cx, cy = x + w // 2, y + h // 2
            rect_area = w * h
            rectangularity = area / rect_area if rect_area > 0 else 0
            confidence = rectangularity
            detections.append(
                DetectedSample(pixel_x=cx, pixel_y=cy, width=w, height=h, confidence=confidence)
            )
        return detections

    def _filter_by_distance(self, detections: List[DetectedSample], min_distance: int) -> List[DetectedSample]:
        if not detections:
            return []
        filtered: List[DetectedSample] = []
        for d in detections:
            too_close = False
            for existing in filtered:
                dist = np.sqrt(
                    (d.pixel_x - existing.pixel_x) ** 2
                    + (d.pixel_y - existing.pixel_y) ** 2
                )
                if dist < min_distance:
                    if d.confidence > existing.confidence:
                        filtered.remove(existing)
                    else:
                        too_close = True
                    break
            if not too_close:
                filtered.append(d)
        return filtered

    def _sort_grid_order(self, detections: List[DetectedSample]) -> List[DetectedSample]:
        if not detections:
            return []
        sorted_by_y = sorted(detections, key=lambda d: d.pixel_y)
        if len(sorted_by_y) < 2:
            return sorted_by_y
        y_diffs = [sorted_by_y[i + 1].pixel_y - sorted_by_y[i].pixel_y for i in range(len(sorted_by_y) - 1)]
        row_threshold = np.median(y_diffs) * 0.5 if y_diffs else 50
        rows = []
        current_row = [sorted_by_y[0]]
        for d in sorted_by_y[1:]:
            if d.pixel_y - current_row[-1].pixel_y < row_threshold:
                current_row.append(d)
            else:
                rows.append(sorted(current_row, key=lambda x: x.pixel_x))
                current_row = [d]
        rows.append(sorted(current_row, key=lambda x: x.pixel_x))
        return [d for row in rows for d in row]

    def _assign_labels(self, detections: List[DetectedSample]) -> List[DetectedSample]:
        if not detections:
            return []
        sorted_by_y = sorted(detections, key=lambda d: d.pixel_y)
        if len(sorted_by_y) < 2:
            sorted_by_y[0].label = "A1"
            return sorted_by_y
        y_coords = [d.pixel_y for d in sorted_by_y]
        y_diffs = [y_coords[i + 1] - y_coords[i] for i in range(len(y_coords) - 1)]
        row_threshold = np.median(y_diffs) * 0.5 if y_diffs else 50
        rows = []
        current_row = [sorted_by_y[0]]
        for d in sorted_by_y[1:]:
            if d.pixel_y - current_row[-1].pixel_y < row_threshold:
                current_row.append(d)
            else:
                rows.append(sorted(current_row, key=lambda x: x.pixel_x))
                current_row = [d]
        rows.append(sorted(current_row, key=lambda x: x.pixel_x))
        for row_idx, row in enumerate(rows):
            row_letter = chr(ord("A") + row_idx)
            for col_idx, detection in enumerate(row):
                detection.label = f"{row_letter}{col_idx + 1}"
        return [d for row in rows for d in row]

    def draw_detections(
        self,
        image: np.ndarray,
        detections: List[DetectedSample],
        color: Tuple[int, int, int] = (0, 255, 0),
        thickness: int = 2,
    ) -> np.ndarray:
        output = image.copy()
        for d in detections:
            if getattr(d, "radius", None):
                cv2.circle(output, (d.pixel_x, d.pixel_y), d.radius, color, thickness)
            elif getattr(d, "width", None) and getattr(d, "height", None):
                x1 = d.pixel_x - d.width // 2
                y1 = d.pixel_y - d.height // 2
                x2 = d.pixel_x + d.width // 2
                y2 = d.pixel_y + d.height // 2
                cv2.rectangle(output, (x1, y1), (x2, y2), color, thickness)
            else:
                size = 10
                cv2.line(output, (d.pixel_x - size, d.pixel_y),
                         (d.pixel_x + size, d.pixel_y), color, thickness)
                cv2.line(output, (d.pixel_x, d.pixel_y - size),
                         (d.pixel_x, d.pixel_y + size), color, thickness)
            if getattr(d, "label", None):
                cv2.putText(
                    output,
                    d.label,
                    (d.pixel_x + 5, d.pixel_y - 5),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    0.5,
                    color,
                    1,
                )
        return output


def main():
    try:
        detector = SampleDetector()
        detections, image = detector.find_samples(IMAGE_PATH)

        print(f"\nDetected {len(detections)} samples:")
        print("-" * 60)
        for i, d in enumerate(detections, 1):
            pos = f"({d.pixel_x}, {d.pixel_y})"
            if getattr(d, "radius", None):
                size = f"r={d.radius}"
            elif getattr(d, "width", None) and getattr(d, "height", None):
                size = f"{d.width}x{d.height}"
            else:
                size = "?"
            label = d.label if getattr(d, "label", None) else "NA"
            print(f"{i:2d}. {label:3s} {pos:12s} {size:8s} conf={d.confidence:.2f}")

        overlay = detector.draw_detections(image, detections)
        ok = cv2.imwrite(OUTPUT_PATH, overlay)
        if ok:
            print(f"\nSaved overlay image to: {OUTPUT_PATH}")
        else:
            print("\nFailed to save overlay image.")

    except Exception as e:
        print(f"Error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
