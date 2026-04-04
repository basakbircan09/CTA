import cv2
import numpy as np
from PySide6.QtWidgets import QLabel
from PySide6.QtGui import QPixmap, QImage
from PySide6.QtCore import Qt


class ImageViewer(QLabel):
    """Image display widget with OpenCV-to-Qt conversion."""

    def __init__(self, parent=None):
        super().__init__("Live / captured / processed image will appear here", parent)
        self.setAlignment(Qt.AlignCenter)
        self.setStyleSheet("""
            QLabel {
                background-color: #1a1a1a;
                color: #666;
                border: 2px solid #333;
                border-radius: 8px;
                font-size: 14px;
            }
        """)
        self.setMinimumSize(800, 500)

    def cv_to_qpixmap(self, img_bgr: np.ndarray) -> QPixmap:
        img_rgb = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2RGB)
        h, w, ch = img_rgb.shape
        bytes_per_line = ch * w
        qimg = QImage(img_rgb.data, w, h, bytes_per_line, QImage.Format_RGB888)
        pix = QPixmap.fromImage(qimg)
        return pix.scaled(
            self.width(),
            self.height(),
            Qt.KeepAspectRatio,
            Qt.SmoothTransformation,
        )

    def show_cv_image(self, img_bgr: np.ndarray):
        pix = self.cv_to_qpixmap(img_bgr)
        self.setPixmap(pix)
