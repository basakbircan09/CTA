"""
Camera acquisition manager built on top of a Qt timer.
"""

from __future__ import annotations

import time
from typing import Optional

from PySide6.QtCore import QObject, QTimer, Signal

from devices.thorlabs_camera import ThorlabsCameraAdapter
from models.frame import Frame


class AcquisitionThread(QObject):
    """
    Continuously polls the camera for new frames using a QTimer.

    Despite the name, this implementation remains within the GUI thread to avoid
    thread-safety issues with the underlying SDK. The public API matches the
    previous QThread-based implementation.
    """

    frame_ready = Signal(object)
    fps_updated = Signal(float)
    error = Signal(str)

    def __init__(
        self,
        camera: ThorlabsCameraAdapter,
        poll_interval_ms: int = 10,
        parent: Optional[QObject] = None,
    ) -> None:
        super().__init__(parent)
        self._camera = camera
        self._timer = QTimer(self)
        self._timer.setInterval(max(1, poll_interval_ms))
        self._timer.timeout.connect(self._poll_camera)

        self._last_fps_time = 0.0
        self._frame_count = 0

    def start_stream(self) -> None:
        if self._timer.isActive():
            return
        try:
            self._camera.start_acquisition()
        except Exception as exc:
            self.error.emit(str(exc))
            return
        self._last_fps_time = time.perf_counter()
        self._frame_count = 0
        self._timer.start()

    def stop_stream(self) -> None:
        if self._timer.isActive():
            self._timer.stop()
        if self._camera.is_acquiring:
            try:
                self._camera.stop_acquisition()
            except Exception as exc:
                self.error.emit(str(exc))

    def _poll_camera(self) -> None:
        try:
            frame = self._camera.read_latest_frame()
        except Exception as exc:
            self.error.emit(str(exc))
            self.stop_stream()
            return

        if frame is None:
            return

        self.frame_ready.emit(frame)
        self._frame_count += 1
        now = time.perf_counter()
        elapsed = now - self._last_fps_time
        if elapsed >= 1.0:
            fps = self._frame_count / elapsed
            self.fps_updated.emit(fps)
            self._frame_count = 0
            self._last_fps_time = now

    @property
    def running(self) -> bool:
        return self._timer.isActive()
