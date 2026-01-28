
from __future__ import annotations

import numpy as np
import pytest

pytest.importorskip("pytestqt")

from PySide6.QtCore import QObject, Signal

from app.controller import ApplicationController
from devices.thorlabs_camera import ThorlabsCameraAdapter
from gui.main_window import MainWindow
from models.frame import Frame
from services.storage import FrameSaver
from tests.fixtures import MockThorlabsCamera


class FakeAcquisitionThread(QObject):
    frame_ready = Signal(Frame)
    fps_updated = Signal(float)
    error = Signal(str)

    def __init__(self, camera):
        super().__init__()
        self.camera = camera
        self.running = False

    def start_stream(self):
        self.running = True

    def stop_stream(self):
        self.running = False


@pytest.fixture
def mock_adapter():
    factory = lambda serial=None: MockThorlabsCamera(serial or "SIM123")
    lister = lambda: ["SIM123"]
    return ThorlabsCameraAdapter(camera_factory=factory, camera_lister=lister)


def test_controller_initialize_and_snapshot(qtbot, tmp_path, mock_adapter):
    window = MainWindow()
    qtbot.addWidget(window)

    controller = ApplicationController(
        camera_adapter=mock_adapter,
        frame_saver=FrameSaver(tmp_path),
        acquisition_thread_factory=FakeAcquisitionThread,
        main_window=window,
        dll_setup=lambda path: None,
    )

    assert controller.initialize()
    assert controller.current_settings is not None
    assert not controller.camera.is_acquiring

    controller.start_live()
    assert controller.acquisition_thread.running
    controller.stop_live()
    assert not controller.acquisition_thread.running

    # Simulate incoming frame and snapshot
    data = (np.ones((10, 10, 3), dtype=np.uint16) * 2000)
    frame = Frame(data=data, timestamp_ns=1, frame_index=1)
    controller._on_frame_ready(frame)
    controller.capture_snapshot()

    saved_files = list(tmp_path.glob("*.png"))
    assert len(saved_files) == 1
