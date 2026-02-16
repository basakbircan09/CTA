# GUI Layer Overview

## Widgets
- gui/live_view.py: LiveViewWidget converts numpy frames to QImage for display and shows frame metadata.
- gui/camera_controls.py: CameraControlPanel exposes exposure/gain sliders and buttons for start/stop/snapshot via Qt signals.
- gui/white_balance_panel.py: WhiteBalancePanel handles preset selection and manual RGB gain tweaks, emitting updated gains.
- gui/focus_assistant.py: FocusAssistantWidget renders the current focus metric as text and a progress bar.
- gui/settings_manager.py: SettingsManagerWidget lists preset JSON files, offers helper methods for save/load/delete, and emits signals for controller coordination.
- gui/main_window.py: MainWindow composes all widgets, re-emits user actions, and provides helpers to update the live view/focus/status.

## Testing
- GUI unit tests live in `tests/unit/test_gui_widgets.py`. They require pytest-qt; if the plugin is missing the tests are skipped automatically. Run manually with:
  ```
  python -m pip install pytest-qt
  python -m pytest tests/unit/test_gui_widgets.py
  ```

## Dependencies
- PySide6 must be installed for GUI components.
- GUI tests run headless by forcing `QT_QPA_PLATFORM=offscreen` (configured in `tests/conftest.py`).

## Usage Notes
- `SettingsManagerWidget` defaults to `config.PRESETS_DIR` but accepts a custom directory for testing or multi-user setups.
- `MainWindow` exposes Qt signals so an application controller can connect business logic without the window importing service-layer classes directly.
- The preset manager is currently instantiated but hidden in the UI to keep the early workflow focused on live view; presets remain available via JSON files for later use.
- Launch the integrated application with: `python -m app.main` (ensure the camera is connected and DLL path configured).
