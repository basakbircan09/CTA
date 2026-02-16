# Keyboard Shortcuts

Quick reference for keyboard shortcuts in the Thorlabs Camera Control application.

**All shortcuts validated and working!** ✅

## Live View Control

| Shortcut | Action | Description |
|----------|--------|-------------|
| **Space** | Toggle Live View | Start or stop camera acquisition. Press once to start, press again to stop. |
| **Ctrl+S** | Capture Snapshot | Save current frame to `snapshots/` directory. Works whenever a frame is available (live view recommended). |

## User Interface

| Shortcut | Action | Description |
|----------|--------|-------------|
| **Ctrl+H** | Toggle Controls Panel | Hide or show the right-side control panel for full-screen imaging view. Press again to restore controls at 75/25 split ratio. (H for "Hide") |
| **Ctrl+Q** | Quit Application | Close the application. Automatically stops acquisition and disconnects camera. |
| **F1** | Show Help | Open the in-app quick reference covering workflow tips, presets, and shortcuts. |

## Usage Tips

### Focus Workflow
1. Press **Space** to start live view
2. Manually adjust camera lens while watching focus assistant bar
3. Press **Ctrl+H** to hide controls for better view of image
4. When focused, press **Ctrl+H** to restore controls
5. Adjust exposure/gain if needed
6. Press **Ctrl+S** to capture snapshots as needed
7. Press **F1** anytime for a refresher on controls and shortcuts

### Full-Screen Imaging
1. Start live view with **Space**
2. Press **Ctrl+H** to hide controls → imaging area expands to full window
3. Drag window border to maximize screen usage
4. Press **Ctrl+S** to capture frames as needed
5. Press **Ctrl+H** when you need to adjust settings

### Quick Exit
- Press **Ctrl+Q** at any time to close application
- All cleanup (stop acquisition, disconnect camera) happens automatically

### UI Hints
- Hover over sliders, spin boxes, and buttons to read context-sensitive tooltips explaining best practices
- Status tips mirror these hints in the status bar when controls are focused

## Platform-Specific Notes

### Windows
- All shortcuts work as documented
- **Ctrl+Q** closes application
- **Ctrl+H** does not conflict with browser history (application-specific)

### macOS / Linux
- **Ctrl** shortcuts may use **Cmd** on macOS
- **Ctrl+Q** follows platform conventions
- **Ctrl+H** may conflict with system shortcuts on some platforms

## Future Shortcuts (Planned)

| Shortcut | Action | Status |
|----------|--------|--------|
| Ctrl+O | Load Preset | When settings manager is enabled |
| Ctrl+Shift+S | Save Preset | When settings manager is enabled |
| + / - | Adjust Exposure | Fine-tuning during live view |
| [ / ] | Adjust Gain | Fine-tuning during live view |

## Customization

Keyboard shortcuts are currently hardcoded in `src/gui/main_window.py` in the `_setup_shortcuts()` method. To customize:

1. Edit `src/gui/main_window.py`
2. Modify the `QKeySequence` in `_setup_shortcuts()`
3. Update this documentation

Example:
```python
# Change Space to Ctrl+Space
toggle_live_action.setShortcut(QKeySequence("Ctrl+Space"))
```
