"""
Thorlabs camera adapter built on top of pylablib.

This module hides direct dependencies on pylablib so upper layers can work
with a simple, testable interface. A camera factory and lister can be
injected for unit testing to avoid requiring the actual SDK.
"""

from __future__ import annotations

from pathlib import Path
from typing import Callable, List, Optional, Sequence
import time

import numpy as np

from devices.exceptions import (
    AcquisitionError,
    CameraConfigurationError,
    CameraConnectionError,
    FrameTimeoutError,
)
from models.camera import CameraCapabilities, CameraSettings, ROI
from models.frame import Frame

try:
    import pylablib as pll
    from pylablib.devices import Thorlabs
except ImportError:  # pragma: no cover - exercised via tests with mocks
    pll = None
    Thorlabs = None


def setup_dll_path(dll_dir: Path | str) -> None:
    """
    Configure pylablib to locate the Thorlabs DLLs.

    Parameters
    ----------
    dll_dir:
        Directory containing the Thorlabs native DLLs.
    """
    if pll is None:
        raise CameraConnectionError(
            "pylablib is not available; install pylablib to use the camera adapter."
        )
    pll.par["devices/dlls/thorlabs_tlcam"] = str(dll_dir)


CameraFactory = Callable[[Optional[str]], object]
CameraLister = Callable[[], Sequence[str]]


class ThorlabsCameraAdapter:
    """
    High-level wrapper around pylablib's ThorlabsTLCamera.

    Parameters
    ----------
    camera_factory:
        Callable returning a camera instance for the given serial number.
        Defaults to creating `Thorlabs.ThorlabsTLCamera`.
    camera_lister:
        Callable returning an iterable of available serial numbers.
        Defaults to `Thorlabs.list_cameras_tlcam`.
    """

    def __init__(
        self,
        camera_factory: Optional[CameraFactory] = None,
        camera_lister: Optional[CameraLister] = None,
    ) -> None:
        if camera_factory is None or camera_lister is None:
            if Thorlabs is None:
                raise CameraConnectionError(
                    "pylablib is required when using the default camera implementation."
                )
        self._camera_factory: CameraFactory = camera_factory or (
            lambda serial: Thorlabs.ThorlabsTLCamera(serial=serial)
        )
        self._camera_lister: CameraLister = camera_lister or Thorlabs.list_cameras_tlcam

        self._camera = None
        self._capabilities: Optional[CameraCapabilities] = None
        self._connected_serial: Optional[str] = None
        self._is_acquiring = False
        self._frame_counter = 0
        self._white_balance_rgb = (1.0, 1.0, 1.0)

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------
    def list_cameras(self) -> List[str]:
        """Return the list of discoverable camera serial numbers."""
        serials = list(self._camera_lister() or [])
        return serials

    def connect(self, serial: Optional[str] = None) -> CameraCapabilities:
        """Open a camera and return its capabilities."""
        available = self.list_cameras()
        if not available:
            raise CameraConnectionError("No Thorlabs cameras detected.")

        selected_serial = serial or available[0]
        try:
            camera = self._camera_factory(selected_serial)
        except Exception as exc:  # pragma: no cover - depends on SDK
            raise CameraConnectionError(f"Failed to open camera {selected_serial}: {exc}") from exc

        self._camera = camera
        self._connected_serial = selected_serial
        self._is_acquiring = False
        self._frame_counter = 0

        capabilities = self._read_capabilities()
        self._capabilities = capabilities
        self._white_balance_rgb = (1.0, 1.0, 1.0)
        return capabilities

    def disconnect(self) -> None:
        """Close the current camera if one is open."""
        if self._camera is None:
            return
        try:
            if self._is_acquiring:
                try:
                    self._camera.stop_acquisition()
                except Exception:
                    pass
            self._camera.close()
        finally:
            self._camera = None
            self._capabilities = None
            self._connected_serial = None
            self._is_acquiring = False

    def __enter__(self) -> "ThorlabsCameraAdapter":  # pragma: no cover
        return self

    def __exit__(self, exc_type, exc, tb) -> None:  # pragma: no cover
        self.disconnect()

    # ------------------------------------------------------------------
    # Properties
    # ------------------------------------------------------------------
    @property
    def is_connected(self) -> bool:
        return self._camera is not None

    @property
    def is_acquiring(self) -> bool:
        return self._is_acquiring

    @property
    def capabilities(self) -> Optional[CameraCapabilities]:
        return self._capabilities

    @property
    def camera(self):
        """Expose the underlying camera for advanced scenarios/testing."""
        return self._camera

    # ------------------------------------------------------------------
    # Configuration
    # ------------------------------------------------------------------
    def apply_settings(self, settings: CameraSettings) -> CameraSettings:
        """Apply camera settings and return the actual values set."""
        camera = self._require_camera()

        try:
            camera.set_exposure(settings.exposure_sec)
            camera.set_gain(settings.gain_db)
        except Exception as exc:
            raise CameraConfigurationError(f"Failed to set exposure/gain: {exc}") from exc

        if settings.roi:
            roi_tuple = settings.roi.to_pylablib()
            try:
                camera.set_roi(*roi_tuple)
            except Exception as exc:
                raise CameraConfigurationError(f"Failed to set ROI: {exc}") from exc

        self._white_balance_rgb = settings.white_balance_rgb

        actual_roi = None
        try:
            actual_roi_tuple = camera.get_roi()
            if actual_roi_tuple is not None:
                actual_roi = ROI.from_pylablib(actual_roi_tuple)
        except Exception:
            actual_roi = settings.roi

        actual_settings = CameraSettings(
            exposure_sec=float(camera.get_exposure()),
            gain_db=float(camera.get_gain()),
            roi=actual_roi,
            white_balance_rgb=settings.white_balance_rgb,
        )
        return actual_settings

    def get_current_settings(self) -> CameraSettings:
        """Return current camera settings."""
        camera = self._require_camera()
        roi = None
        try:
            roi_tuple = camera.get_roi()
            if roi_tuple is not None:
                roi = ROI.from_pylablib(roi_tuple)
        except Exception:
            roi = None

        return CameraSettings(
            exposure_sec=float(camera.get_exposure()),
            gain_db=float(camera.get_gain()),
            roi=roi,
            white_balance_rgb=self._white_balance_rgb,
        )

    # ------------------------------------------------------------------
    # Acquisition
    # ------------------------------------------------------------------
    def start_acquisition(self) -> None:
        camera = self._require_camera()
        try:
            camera.start_acquisition()
        except Exception as exc:
            raise AcquisitionError(f"Failed to start acquisition: {exc}") from exc
        self._is_acquiring = True
        self._frame_counter = 0

    def stop_acquisition(self) -> None:
        if not self._is_acquiring:
            return
        camera = self._require_camera()
        try:
            camera.stop_acquisition()
        except Exception as exc:
            raise AcquisitionError(f"Failed to stop acquisition: {exc}") from exc
        finally:
            self._is_acquiring = False

    def read_latest_frame(self) -> Optional[Frame]:
        """Fetch the newest available frame, or None if no frame is ready."""
        camera = self._require_camera()
        try:
            image = camera.read_newest_image()
        except Exception as exc:
            raise FrameTimeoutError(f"Failed to read frame: {exc}") from exc

        if image is None:
            return None

        data = np.array(image, copy=True)
        frame = Frame(
            data=data,
            timestamp_ns=time.time_ns(),
            frame_index=self._frame_counter,
            metadata={
                "exposure_sec": float(camera.get_exposure()),
                "gain_db": float(camera.get_gain()),
                "white_balance_rgb": self._white_balance_rgb,
            },
        )
        self._frame_counter += 1
        return frame

    def snap(self) -> Frame:
        """Capture a single frame using the camera's snap function."""
        camera = self._require_camera()
        try:
            data = np.array(camera.snap(), copy=True)
        except Exception as exc:
            raise AcquisitionError(f"Failed to snap frame: {exc}") from exc

        frame = Frame(
            data=data,
            timestamp_ns=time.time_ns(),
            frame_index=self._frame_counter,
            metadata={
                "exposure_sec": float(camera.get_exposure()),
                "gain_db": float(camera.get_gain()),
                "white_balance_rgb": self._white_balance_rgb,
            },
        )
        self._frame_counter += 1
        return frame

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------
    def _require_camera(self):
        if self._camera is None:
            raise CameraConnectionError("Camera is not connected.")
        return self._camera

    def _read_capabilities(self) -> CameraCapabilities:
        camera = self._require_camera()

        model, _name, serial, firmware = camera.get_device_info()
        sensor_width, sensor_height = camera.get_detector_size()
        sensor_info = camera.get_sensor_info()
        sensor_type = self._parse_sensor_info(sensor_info)

        bit_depth = None
        if hasattr(camera, "get_bit_depth"):
            try:
                bit_depth = int(camera.get_bit_depth())
            except Exception:
                bit_depth = None
        if bit_depth is None:
            bit_depth = 16

        exposure_range = self._get_range(
            camera,
            candidates=("get_exposure_range", "get_exposure_limits"),
            default=(1e-6, 10.0),
        )
        gain_range = self._get_range(
            camera,
            candidates=("get_gain_range", "get_gain_limits"),
            default=(0.0, 24.0),
        )

        return CameraCapabilities(
            model=model,
            serial=serial,
            firmware=firmware,
            sensor_width=int(sensor_width),
            sensor_height=int(sensor_height),
            sensor_type=sensor_type,
            bit_depth=bit_depth,
            exposure_range_sec=exposure_range,
            gain_range_db=gain_range,
        )

    @staticmethod
    def _parse_sensor_info(sensor_info: object) -> str:
        if isinstance(sensor_info, dict):
            return str(sensor_info.get("type", "unknown")).lower()
        if isinstance(sensor_info, (list, tuple)) and sensor_info:
            return str(sensor_info[0]).lower()
        return str(sensor_info).lower() if sensor_info else "unknown"

    @staticmethod
    def _get_range(camera, candidates, default):
        for name in candidates:
            func = getattr(camera, name, None)
            if callable(func):
                try:
                    values = func()
                except Exception:
                    continue
                if isinstance(values, (list, tuple)) and len(values) >= 2:
                    try:
                        return (float(values[0]), float(values[1]))
                    except (TypeError, ValueError):
                        continue
        return (float(default[0]), float(default[1]))
