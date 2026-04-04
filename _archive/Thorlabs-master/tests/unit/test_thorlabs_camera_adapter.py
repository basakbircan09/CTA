
from __future__ import annotations

import types
import pytest

from devices import thorlabs_camera as adapter_module
from devices.exceptions import CameraConnectionError
from devices.thorlabs_camera import ThorlabsCameraAdapter
from models.camera import CameraSettings, ROI
from tests.fixtures import MockThorlabsCamera


class AlternateRangeMock(MockThorlabsCamera):
    def get_exposure_range(self):
        raise AttributeError("use limits")

    def get_gain_range(self):
        raise AttributeError("use limits")

    def get_exposure_limits(self):
        return (0.002, 5.0)

    def get_gain_limits(self):
        return (0.5, 18.0)


def test_setup_dll_path_updates_parameter(monkeypatch):
    dummy_pll = types.SimpleNamespace(par={})
    monkeypatch.setattr(adapter_module, "pll", dummy_pll)
    adapter_module.setup_dll_path("C:/dlls")
    assert dummy_pll.par["devices/dlls/thorlabs_tlcam"] == "C:/dlls"


def test_setup_dll_path_requires_pylablib(monkeypatch):
    monkeypatch.setattr(adapter_module, "pll", None)
    with pytest.raises(CameraConnectionError):
        adapter_module.setup_dll_path("C:/dlls")


@pytest.fixture
def camera_lister():
    return lambda: ["SIM123"]


@pytest.fixture
def camera_factory():
    return lambda serial=None: MockThorlabsCamera(serial or "SIM123")


@pytest.fixture
def adapter(camera_factory, camera_lister):
    return ThorlabsCameraAdapter(
        camera_factory=camera_factory,
        camera_lister=camera_lister,
    )


def test_connect_populates_capabilities(adapter):
    caps = adapter.connect()
    assert caps.serial == "SIM123"
    assert caps.sensor_width == 640
    assert caps.sensor_height == 480
    assert adapter.is_connected
    assert adapter.capabilities == caps


def test_list_cameras_uses_lister(adapter, camera_lister):
    assert adapter.list_cameras() == ["SIM123"]


def test_connect_without_available_camera_raises(camera_factory):
    empty_lister = lambda: []
    adapter = ThorlabsCameraAdapter(
        camera_factory=camera_factory,
        camera_lister=empty_lister,
    )
    with pytest.raises(CameraConnectionError):
        adapter.connect()


def test_capabilities_fallback_methods():
    factory = lambda serial=None: AlternateRangeMock(serial or "SIM999")
    lister = lambda: ["SIM999"]
    adapter = ThorlabsCameraAdapter(camera_factory=factory, camera_lister=lister)
    caps = adapter.connect()
    assert caps.exposure_range_sec == (0.002, 5.0)
    assert caps.gain_range_db == (0.5, 18.0)


def test_apply_settings_updates_camera(adapter):
    adapter.connect()
    roi = ROI(x=10, y=20, width=100, height=80)
    settings = CameraSettings(
        exposure_sec=0.05,
        gain_db=6.0,
        roi=roi,
        white_balance_rgb=(0.8, 1.0, 1.2),
    )

    applied = adapter.apply_settings(settings)
    camera = adapter.camera

    assert pytest.approx(camera.get_exposure(), rel=1e-6) == 0.05
    assert pytest.approx(camera.get_gain(), rel=1e-6) == 6.0
    assert camera.get_roi() == roi.to_pylablib()

    assert applied.roi == roi
    assert applied.white_balance_rgb == (0.8, 1.0, 1.2)


def test_get_current_settings_reflects_camera_state(adapter):
    adapter.connect()
    roi = ROI(x=0, y=0, width=200, height=150)
    adapter.apply_settings(
        CameraSettings(
            exposure_sec=0.02,
            gain_db=3.0,
            roi=roi,
            white_balance_rgb=(1.0, 1.0, 1.0),
        )
    )

    current = adapter.get_current_settings()
    assert current.roi == roi
    assert pytest.approx(current.exposure_sec, rel=1e-6) == 0.02
    assert pytest.approx(current.gain_db, rel=1e-6) == 3.0


def test_acquisition_cycle(adapter):
    adapter.connect()
    adapter.start_acquisition()
    frame1 = adapter.read_latest_frame()
    assert frame1 is not None
    assert frame1.frame_index == 0
    frame2 = adapter.read_latest_frame()
    assert frame2 is not None
    assert frame2.frame_index == 1
    adapter.stop_acquisition()
    assert adapter.is_acquiring is False


def test_read_latest_frame_returns_none_when_not_ready(adapter):
    adapter.connect()
    frame = adapter.read_latest_frame()
    assert frame is None


def test_snap_captures_frame_without_acquisition(adapter):
    adapter.connect()
    frame = adapter.snap()
    assert frame.frame_index == 0
    assert frame.data.shape == (480, 640, 3)


def test_disconnect_closes_camera(adapter):
    caps = adapter.connect()
    mock_cam = adapter.camera
    adapter.start_acquisition()
    adapter.disconnect()
    assert adapter.is_connected is False
    assert adapter.capabilities is None
    assert mock_cam.closed is True
    assert adapter.camera is None
