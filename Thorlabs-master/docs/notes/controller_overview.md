# Application Controller Overview

- The controller lives in `src/app/controller.py` and coordinates the camera adapter, acquisition poller, processing services, and GUI.
- Dependencies can be injected for testing (camera adapter, frame saver, acquisition poller factory, DLL loader) so integration logic remains testable without hardware.
- Initialization flow:
  1. Configure the DLL search path with `setup_dll_path`.
  2. Discover and connect to the first available Thorlabs camera.
  3. Read current settings, apply default white-balance gains, and prepare the acquisition poller.
  4. Create (or reuse) a `MainWindow`, connect its signals, and push initial settings to the UI.
- Runtime flow:
  - `start_live()` applies the latest `CameraSettings` and starts the acquisition poller.
  - Frames are white-balanced, displayed, and scored using the focus metric; the most recent frame is cached for snapshots.
  - Snapshots are saved to `config.SNAPSHOTS_DIR` via `FrameSaver.save_png()` (with auto-scaling to 8-bit for readability).
  - Preset helpers remain available programmatically even though the widget is currently hidden to keep the UI minimal during early development.
- `app/main.py` launches Qt, instantiates the controller, and shuts everything down cleanly on exit.
