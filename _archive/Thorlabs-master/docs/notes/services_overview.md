# Services Layer Overview

## Modules Added
- `src/services/acquisition.py`: `AcquisitionThread` wraps the camera adapter in a Qt `QThread`, emitting `frame_ready`, `fps_updated`, and `error` signals. Call `start_stream()`/`stop_stream()` to control capture loops.
- `src/services/white_balance.py`: `WhiteBalanceProcessor` applies RGB gain factors to `Frame` data.
- `src/services/focus_assistant.py`: `FocusMetric.compute()` returns a sharpness score (uses OpenCV Laplacian when available, falls back to numpy gradients).
- `src/services/storage.py`: `FrameSaver` writes PNG (always available) and TIFF (requires `tifffile`) outputs into a target directory.

## Dependencies
- PySide6 is required for the acquisition thread (Qt event loop).
- Optional: `opencv-python` enhances focus metric accuracy; otherwise a numpy fallback is used.
- Optional: `tifffile` enables TIFF export; if missing, `FrameSaver.save_tiff()` raises a `RuntimeError` and corresponding tests are skipped.
- Testing: the acquisition unit test requires the `pytest-qt` plugin; when absent, it is auto-skipped.

## Testing Summary
- `python -m pytest tests/unit` covers adapter + service modules. Tests auto-skip features when optional dependencies are not installed.
- Hardware verification remains manual via `docs/testing/HARDWARE_TEST.md` once the real camera is connected.
