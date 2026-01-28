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
        # White balance RGB gains (applied in software)
        self._white_balance = (1.0, 1.0, 1.0)

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
            # Apply white balance if not default (1,1,1)
            if self._white_balance != (1.0, 1.0, 1.0):
                data = self._apply_white_balance(data)
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

    # ---------- Camera Settings ----------

    def get_exposure(self) -> float:
        """Get current exposure time in seconds."""
        if not self._connected or self._cam is None:
            raise RuntimeError("Camera not connected")
        return self._cam.get_exposure()

    def set_exposure(self, exposure_sec: float) -> None:
        """Set exposure time in seconds."""
        if not self._connected or self._cam is None:
            raise RuntimeError("Camera not connected")
        self._cam.set_exposure(exposure_sec)

    def get_gain(self) -> float:
        """Get current gain value."""
        if not self._connected or self._cam is None:
            raise RuntimeError("Camera not connected")
        if hasattr(self._cam, "get_gain"):
            return self._cam.get_gain()
        return 0.0

    def set_gain(self, gain: float) -> None:
        """Set gain value."""
        if not self._connected or self._cam is None:
            raise RuntimeError("Camera not connected")
        if hasattr(self._cam, "set_gain"):
            self._cam.set_gain(gain)

    # ---------- White Balance (Software) ----------

    def get_white_balance(self) -> tuple[float, float, float]:
        """Get current white balance RGB gains."""
        return self._white_balance

    def set_white_balance(self, red: float, green: float, blue: float) -> None:
        """Set white balance RGB gains (0.1 to 4.0 per channel)."""
        self._white_balance = (
            max(0.1, min(4.0, red)),
            max(0.1, min(4.0, green)),
            max(0.1, min(4.0, blue))
        )

    def _apply_white_balance(self, frame: np.ndarray) -> np.ndarray:
        """Apply white balance gains to a BGR frame."""
        if frame.ndim != 3 or frame.shape[2] != 3:
            return frame
        # BGR order: index 0=Blue, 1=Green, 2=Red
        gains = np.array([self._white_balance[2], self._white_balance[1], self._white_balance[0]],
                         dtype=np.float32).reshape(1, 1, 3)
        float_data = frame.astype(np.float32) * gains
        return np.clip(float_data, 0, 255).astype(np.uint8)
