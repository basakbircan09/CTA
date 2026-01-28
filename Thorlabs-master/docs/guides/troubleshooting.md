# Troubleshooting Guide

Common issues and solutions for the Thorlabs Camera Control Application.

---

## Startup Issues

### Camera Not Detected

**Symptom:**
```
CameraConnectionError: No Thorlabs cameras detected.
```

**Solutions:**
1. **Check physical connection**
   - Verify USB cable is securely connected
   - Use USB 3.0 port (blue connector) for best performance
   - Try different USB port if available

2. **Verify ThorCam installation**
   - Open ThorCam software
   - Confirm camera appears in ThorCam
   - If ThorCam doesn't see camera, reinstall drivers

3. **Check camera power**
   - Some cameras have external power requirements
   - Verify power LED is lit
   - Try powered USB hub if insufficient power

4. **Run diagnostic script**
   ```bash
   python scripts/check_camera.py
   ```

**Expected output:**
```
[OK] Camera SDK initialized successfully
[OK] Found 1 camera(s)
[OK] Model: CS165CU (S/N: 33021)
```

---

### DLL Path Error

**Symptom:**
```
Initialization Error: DLL path not found
```

**Solutions:**
1. **Verify ThorCam installation path**
   - Default: `C:\Program Files\Thorlabs\Scientific Imaging\Scientific Camera Support\`
   - Check `config.py` THORCAM_DLL_PATH matches actual installation

2. **Update config.py**
   ```python
   THORCAM_DLL_PATH = Path(r"C:\Your\Actual\Path\To\ThorCam")
   ```

3. **Check 64-bit Python**
   - ThorCam DLLs are 64-bit only
   - Verify: `python --version` shows x64

---

### Import Errors

**Symptom:**
```
ModuleNotFoundError: No module named 'pylablib'
```

**Solutions:**
1. **Verify virtual environment activated**
   ```bash
   .venv\Scripts\activate  # Windows
   ```

2. **Reinstall dependencies**
   ```bash
   pip install -r requirements.txt
   ```

3. **Check Python version**
   - Requires Python 3.11+
   - Verify: `python --version`

---

## Runtime Issues

### Black Screen / No Image

**Symptom:** Live view shows black screen after clicking "Start Live"

**Solutions:**
1. **Increase exposure**
   - Move exposure slider to 50-100ms
   - Scene may be too dark for current settings

2. **Remove lens cap** (obvious but common!)

3. **Point at lit scene**
   - Camera needs light source
   - Try pointing at monitor or lamp

4. **Increase gain**
   - Set gain to 10-20 dB temporarily
   - Helps diagnose low-light issues

5. **Check white balance**
   - Extreme white balance can darken image
   - Reset to "Default" preset

---

### Acquisition Fails to Start

**Symptom:** Error dialog: "Could not start acquisition"

**Solutions:**
1. **Check logs**
   - Open `logs/app_YYYYMMDD_HHMMSS.log`
   - Look for detailed error message

2. **Camera busy**
   - Close ThorCam if running
   - Only one application can access camera at once
   - Kill stray Python processes: Task Manager → Python.exe

3. **Restart application**
   - Close and reopen application
   - Camera sometimes needs hard reset

4. **Hardware issue**
   - Unplug camera USB cable
   - Wait 10 seconds
   - Reconnect and restart application

---

### Low Frame Rate

**Symptom:** FPS drops below 20 (target is 25-30)

**Solutions:**
1. **Reduce exposure time**
   - Long exposure (>100ms) limits frame rate
   - Formula: Max FPS ≈ 1000 / exposure_ms

2. **Close other applications**
   - CPU-intensive apps compete for resources
   - Check Task Manager for high CPU usage

3. **USB connection**
   - Use USB 3.0 port (not USB 2.0)
   - Avoid USB hubs if possible
   - Try different USB port

4. **Window size**
   - Smaller window = less rendering overhead
   - Maximize controls panel to reduce imaging area

5. **Check system resources**
   - Monitor CPU usage (should be <50%)
   - Monitor RAM usage (should have >2GB free)

---

### Snapshot Save Fails

**Symptom:** Error dialog: "Could not save frame to disk"

**Solutions:**
1. **Check disk space**
   - Verify free space: `dir data\snapshots`
   - Each snapshot ~6MB (1440x1080 RGB PNG)

2. **Permissions**
   - Ensure write access to `data/snapshots/` directory
   - Run as administrator if needed

3. **No frame available**
   - Must start live view before capturing snapshot
   - Status message: "No frame available. Start live view first."

4. **Invalid characters in filename**
   - Automatic timestamps should prevent this
   - Check `data/snapshots/` for corrupted files

---

### Preset Load/Save Fails

**Symptom:** Error: "Could not save/load preset"

**Solutions:**
1. **Check presets directory**
   - Verify `data/presets/` exists
   - Application creates automatically, but may fail on restricted systems

2. **Invalid preset name**
   - Use alphanumeric characters only
   - Avoid special characters (except underscore/dash)

3. **Corrupted JSON**
   - Open preset file in text editor
   - Verify valid JSON format
   - Delete and recreate if corrupted

---

## GUI Issues

### Window Size Problems

**Symptom:** Window too large/small, controls not visible

**Solutions:**
1. **Resize splitter**
   - Drag border between image and controls
   - Or press **Ctrl+H** to toggle controls

2. **Reset window**
   - Close application
   - Delete settings cache (future feature)
   - Restart application

3. **High DPI displays**
   - Windows: Check display scaling (Settings → Display)
   - 150% scaling recommended for 4K monitors

---

### Keyboard Shortcuts Not Working

**Symptom:** Pressing Space/Ctrl+S has no effect

**Solutions:**
1. **Focus application window**
   - Click on main window
   - Shortcuts require application focus

2. **Modal dialog open**
   - Close error/warning dialogs
   - Shortcuts disabled when dialogs are open

3. **Check keyboard layout**
   - Non-US keyboards may have different key mappings
   - Verify Ctrl key is working: try Ctrl+C to copy

---

### Focus Score Always Zero

**Symptom:** Focus assistant shows 0.0 continuously

**Solutions:**
1. **Start live view**
   - Focus score only updates during acquisition
   - Click "Start Live" or press Space

2. **Completely black/white image**
   - No edges to detect = zero score
   - Adjust exposure to show scene detail

3. **Out of focus**
   - Very blurry images may score near zero
   - Manually adjust lens while watching score increase

---

## Error Messages

### "ACQUISITION ERROR: [message]"

**Persistent status bar error message**

**Causes:**
1. **Hardware timeout**
   - Camera failed to deliver frame within timeout
   - Rare (~0.1% of frames)

2. **USB communication error**
   - Cable issue or USB controller problem
   - More common with USB 2.0 connections

3. **Driver crash**
   - Thorlabs DLL internal error
   - Requires application restart

**Solutions:**
1. **Stop acquisition** (automatic)
   - Application stops automatically on error
   - Error message persists in status bar

2. **Restart live view**
   - Click "Start Live" again
   - Usually works on retry

3. **Check logs**
   - Open `logs/` directory
   - Look for pattern of errors
   - Single errors are normal, repeated errors indicate problem

4. **Restart application**
   - If errors persist, close and reopen
   - Camera hardware reset

5. **Hardware diagnostics**
   - Run ThorCam to verify camera health
   - Check for firmware updates

---

## Performance Issues

### Memory Leak

**Symptom:** RAM usage increases over time

**Solutions:**
1. **Expected behavior**
   - Some growth is normal (frame buffering)
   - Should stabilize after ~100 frames

2. **Excessive growth**
   - >100MB/minute indicates leak
   - Report as bug with logs attached

3. **Workaround**
   - Restart application periodically
   - Stop/start acquisition to clear buffers

---

### CPU Usage High

**Symptom:** CPU usage >50% continuously

**Causes:**
1. **High frame rate**
   - 30 FPS with image processing is CPU-intensive
   - Expected on older systems

2. **White balance processing**
   - RGB gain calculation for each frame
   - Unavoidable overhead

**Solutions:**
1. **Reduce frame rate**
   - Increase exposure time
   - Lower FPS = lower CPU

2. **Close controls panel**
   - Press Ctrl+H to hide controls
   - Slightly reduces rendering overhead

3. **Upgrade hardware**
   - Recommended: Intel i5 or better
   - 4+ cores preferred

---

## Advanced Diagnostics

### Enable Debug Logging

**Edit `src/app/main.py`:**
```python
logging.basicConfig(
    level=logging.DEBUG,  # Changed from INFO
    ...
)
```

**Restart application** to see detailed logs in `logs/` directory.

---

### Check Camera Health

**Run hardware test:**
```bash
python scripts/check_camera.py
```

**Expected output:**
```
[OK] Camera SDK initialized successfully
[OK] Found 1 camera(s)
[OK] Model: CS165CU (S/N: 33021)
[OK] Sensor: 1440x1080 pixels
[OK] Exposure range: 0.001 - 1000.0 ms
[OK] Gain range: 0.0 - 48.0 dB
```

---

### Run Unit Tests

**Verify software integrity:**
```bash
pytest tests/ -v
```

**Expected:** 25/25 tests passing

**If tests fail:**
- Corrupted installation
- Missing dependencies
- Reinstall: `pip install -r requirements.txt --force-reinstall`

---

## Known Issues

### Sporadic Acquisition Errors

**Status:** Expected behavior
**Frequency:** ~0.1% of frames
**Cause:** Thorlabs SDK internal timeout
**Solution:** Application automatically retries
**Impact:** Single frame drop, usually imperceptible

---

### NIR Color Cast

**Status:** Hardware characteristic, not a bug
**Symptom:** Skin appears pink/magenta
**Cause:** CS165CU sensitive to near-infrared (350-1100nm)
**Solution:** Use "Reduce NIR" or "Strong NIR" white balance preset
**Details:** See [color_camera_behavior.md](color_camera_behavior.md)

---

## Getting Help

### Before Reporting Issues

1. **Check this guide** for common solutions
2. **Review logs** in `logs/` directory
3. **Run diagnostics**: `python scripts/check_camera.py`
4. **Verify tests pass**: `pytest tests/`

### Reporting Bugs

**Include:**
1. Error message (full text)
2. Log file from `logs/` directory
3. Steps to reproduce
4. System information:
   - Windows version
   - Python version: `python --version`
   - Camera model
   - USB connection type (2.0 vs 3.0)

**Submit to:** [Repository issues page]

---

## Quick Reference

| Symptom | Quick Fix |
|---------|----------|
| Black screen | Increase exposure to 50-100ms |
| No camera found | Check USB, run `check_camera.py` |
| Low FPS | Reduce exposure, close other apps |
| Save fails | Check disk space and permissions |
| Acquisition error | Restart live view, check logs |
| Shortcut not working | Click window to focus |

---

**Last Updated:** Phase 6 completion (2025-11-05)
