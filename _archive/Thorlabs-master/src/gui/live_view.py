"""
Live view widget displaying camera frames.
"""

from __future__ import annotations

from typing import Optional, Union

import numpy as np
from PySide6.QtCore import Qt
from PySide6.QtGui import QImage, QPixmap
from PySide6.QtWidgets import QLabel, QSizePolicy, QVBoxLayout, QWidget

from models.frame import Frame


class LiveViewWidget(QWidget):
    """Display area for live camera frames."""

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)

        self._image_label = QLabel(self)
        self._image_label.setAlignment(Qt.AlignCenter)
        self._image_label.setStyleSheet("background-color: #000000; border: 1px solid #444;")
        # Set minimum size first (before size policy)
        self._image_label.setMinimumSize(320, 240)
        # Prevent label from expanding to match pixmap size
        # MinimumExpanding: respects minimum, takes available space, but doesn't demand pixmap size
        self._image_label.setSizePolicy(QSizePolicy.MinimumExpanding, QSizePolicy.MinimumExpanding)
        self._image_label.setScaledContents(False)
        self._image_label.setToolTip(
            "Live feed display. Start the camera to view frames; image scales to available space."
        )

        self._info_label = QLabel(self)
        self._info_label.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        self._info_label.setStyleSheet("color: #aaaaaa;")
        self._info_label.setToolTip("Resolution and frame index of the most recent image.")

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self._image_label, stretch=1)
        layout.addWidget(self._info_label)
        self.setToolTip("Displays the current camera image and metadata.")

    def update_frame(self, frame: Union[Frame, np.ndarray]) -> None:
        """Update the display with a new frame."""
        image = frame.data if isinstance(frame, Frame) else frame
        qimage = self._numpy_to_qimage(image)
        if qimage is None:
            return

        pixmap = QPixmap.fromImage(qimage)
        # Scale pixmap to fit label while maintaining aspect ratio
        scaled_pixmap = pixmap.scaled(
            self._image_label.size(),
            Qt.KeepAspectRatio,
            Qt.SmoothTransformation
        )
        self._image_label.setPixmap(scaled_pixmap)

        if isinstance(frame, Frame):
            info_text = f"{frame.width}x{frame.height} px | idx {frame.frame_index}"
        else:
            info_text = f"{image.shape[1]}x{image.shape[0]} px"
        self._info_label.setText(info_text)

    @staticmethod
    def _numpy_to_qimage(data: np.ndarray) -> Optional[QImage]:
        """Convert numpy array to QImage for display."""
        if data.size == 0:
            return None

        if data.ndim == 2:
            image_u8 = LiveViewWidget._to_uint8(data)
            height, width = image_u8.shape
            bytes_per_line = width
            return QImage(
                image_u8.data,
                width,
                height,
                bytes_per_line,
                QImage.Format_Grayscale8,
            ).copy()

        if data.ndim == 3 and data.shape[2] in (3, 4):
            image_u8 = LiveViewWidget._to_uint8(data)
            height, width, channels = image_u8.shape
            bytes_per_line = channels * width

            fmt = QImage.Format_RGBA8888 if channels == 4 else QImage.Format_RGB888
            qimage = QImage(
                image_u8.data,
                width,
                height,
                bytes_per_line,
                fmt,
            )
            if channels == 3:
                return qimage.rgbSwapped()
            return qimage.copy()

        return None

    @staticmethod
    def _to_uint8(array: np.ndarray) -> np.ndarray:
        """Scale array to 8-bit range for display."""
        if array.dtype == np.uint8:
            return array
        if np.issubdtype(array.dtype, np.integer):
            data = array.astype(np.float32)
            min_val = float(data.min())
            max_val = float(data.max())
            if max_val <= min_val:
                return np.zeros_like(array, dtype=np.uint8)
            scaled = (data - min_val) / (max_val - min_val)
            return (scaled * 255.0).clip(0, 255).astype(np.uint8)
        scaled = np.clip(array, 0.0, 1.0)
        return (scaled * 255.0).astype(np.uint8)
