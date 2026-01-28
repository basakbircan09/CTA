from __future__ import annotations

import pytest

pytest.importorskip("pytestqt")

from devices.thorlabs_camera import ThorlabsCameraAdapter
from services.acquisition import AcquisitionThread
from tests.fixtures import MockThorlabsCamera


@pytest.fixture
def adapter():
    factory = lambda serial=None: MockThorlabsCamera(serial or "SIM123")
    lister = lambda: ["SIM123"]
    adapter = ThorlabsCameraAdapter(camera_factory=factory, camera_lister=lister)
    adapter.connect()
    yield adapter
    adapter.disconnect()


def test_acquisition_manager_emits_frames(qtbot, adapter):
    thread = AcquisitionThread(adapter, poll_interval_ms=5)
    thread.start_stream()
    with qtbot.waitSignal(thread.frame_ready, timeout=2000) as blocker:
        pass
    assert blocker.args[0].frame_index == 0

    with qtbot.waitSignal(thread.fps_updated, timeout=2000):
        pass

    thread.stop_stream()
    assert not thread.running
