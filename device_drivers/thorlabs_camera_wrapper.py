from __future__ import annotations

from pathlib import Path
import numpy as np
import cv2

try:
    import pylablib as pll
    from pylablib.devices import Thorlabs
except ImportError:
    pll = None
    Thorlabs = None


class ThorlabsCamera:
    """
    Minimal wrapper around pylablib ThorlabsTLCamera.
    """

    def __init__(self, dll_dir: Path | str | None = None):
        # IMPORTANT: store dll_dir on the instance
        self._dll_dir = dll_dir
        self._cam = None
        self._connected = False

    @property
    def is_connected(self) -> bool:
        """Return whether the camera is connected."""
        return self._connected

    def connect(self):
        if self._connected:
            return

        if Thorlabs is None:
            raise RuntimeError(
                "Thorlabs SDK not available. Install pylablib and the Thorlabs TL camera drivers."
            )

        # Use the per-instance _dll_dir
        if self._dll_dir is not None and pll is not None:
            pll.par["devices/dlls/thorlabs_tlcam"] = str(self._dll_dir)

        serials = list(Thorlabs.list_cameras_tlcam() or [])
        if not serials:
            raise RuntimeError("No Thorlabs cameras detected.")

        serial = serials[0]
        cam = Thorlabs.ThorlabsTLCamera(serial=serial)
        cam.open()

        # Basic settings to avoid black images
        cam.set_exposure(0.1)  # 100 ms to start
        if hasattr(cam, "set_gain"):
            cam.set_gain(0.0)
        try:
            cam.set_roi(0, None, 0, None, 1, 1)
        except Exception:
            pass

        self._cam = cam
        self._connected = True
        print(f"Connected Thorlabs camera S/N {serial}")

    def disconnect(self):
        if not self._connected or self._cam is None:
            return
        try:
            try:
                self._cam.stop_acquisition()
            except Exception:
                pass
            self._cam.close()
        finally:
            self._cam = None
            self._connected = False

    def grab_frame(self) -> np.ndarray:
        """Grab one frame and return as BGR image, preserving color if available."""
        if not self._connected or self._cam is None:
            raise RuntimeError("Camera not connected")

        img = self._cam.snap()
        data = np.array(img, copy=True)

        # Handle normalization based on dimensionality and dtype
        if data.ndim == 3 and data.shape[2] == 3:  # 3D color data (H, W, 3)
            if data.dtype != np.uint8:
                # Normalize each channel separately to avoid color distortion
                if data.dtype == np.uint16:
                    min_v = data.min(axis=(0, 1))
                    max_v = data.max(axis=(0, 1))
                    normalized = np.zeros_like(data, dtype=np.float32)
                    for c in range(3):
                        if max_v[c] > min_v[c]:
                            normalized[:, :, c] = ((data[:, :, c] - min_v[c]) / (max_v[c] - min_v[c]) * 255.0)
                        else:
                            normalized[:, :, c] = 0
                    data = normalized.astype(np.uint8)
                else:
                    data = data.astype(np.uint8)
            # Assume input is BGR or RGB; convert if needed (Thorlabs often outputs RGB, so try both)
            if data.shape[2] == 3:
                # Test for RGB by checking if it looks like valid color (simple heuristic: variance in channels)
                gray_test = cv2.cvtColor(data, cv2.COLOR_BGR2GRAY)
                if np.std(data[:, :, 0] - gray_test) < 10:  # Low variance suggests not color
                    data = cv2.cvtColor(data, cv2.COLOR_RGB2BGR)
            return data  # Return color BGR directly
        elif data.ndim == 2:  # 2D grayscale
            if data.dtype == np.uint16:
                min_v = data.min()
                max_v = data.max()
                if max_v > min_v:
                    gray8 = ((data - min_v) / (max_v - min_v) * 255.0).astype(np.uint8)
                else:
                    gray8 = np.zeros_like(data, dtype=np.uint8)
            else:
                gray8 = data.astype(np.uint8)
            # Convert grayscale to BGR only if needed for consistency
            bgr = cv2.cvtColor(gray8, cv2.COLOR_GRAY2BGR)
            return bgr
        else:
            raise ValueError(f"Unexpected image shape: {data.shape}")

    def save_frame(self, path: str) -> np.ndarray:
        frame_bgr = self.grab_frame()
        cv2.imwrite(path, frame_bgr)
        return frame_bgr
