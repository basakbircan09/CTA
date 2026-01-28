# Phase 6 - Definition of Done Validation Checklist

**Version:** 1.0.0
**Date:** 2025-11-05
**Validator:** _______________

---

## Pre-Validation Setup

- [ ] Virtual environment activated: `.venv\Scripts\activate`
- [ ] Dependencies installed: `pip install -r requirements.txt`
- [ ] Camera connected via USB 3.0
- [ ] ThorCam software verified camera detection
- [ ] No other applications accessing camera

---

## 1. Code Quality

### Test Suite
- [ ] Run: `pytest tests/ -v`
- [ ] **Expected:** 25/25 tests passing
- [ ] **Expected:** No test failures
- [ ] **Expected:** Warnings acceptable (pylablib pkg_resources deprecation only)

### Code Health
- [ ] No syntax errors in `src/` directory
- [ ] All imports resolve correctly
- [ ] Logging configured properly (check `logs/` directory after run)

---

## 2. Error Handling (Task 22)

### Initialization Errors
- [ ] **Test:** Unplug camera, run application
- [ ] **Expected:** Error dialog: "No Thorlabs cameras detected"
- [ ] **Expected:** Application exits gracefully (no crash)
- [ ] **Expected:** Log file created in `logs/` with error details

### Runtime Errors
- [ ] **Test:** Start live view, then disconnect camera USB mid-acquisition
- [ ] **Expected:** Status bar shows: "ACQUISITION ERROR: [message]"
- [ ] **Expected:** Error dialog appears with details
- [ ] **Expected:** Live view stops automatically
- [ ] **Expected:** Can restart application without crash

### Error Recovery
- [ ] **Test:** Cause error, then restart live view
- [ ] **Expected:** Status bar clears previous error
- [ ] **Expected:** Application recovers and works normally

### Logging Verification
- [ ] Open latest log file in `logs/` directory
- [ ] **Expected:** Initialization logged with timestamps
- [ ] **Expected:** Errors logged with `exc_info=True` (full stack trace)
- [ ] **Expected:** Both file and console logging active

---

## 3. Keyboard Shortcuts (Task 23)

### Space - Toggle Live View
- [ ] **Test:** Press Space (not running)
- [ ] **Expected:** Live view starts, imaging area shows camera feed
- [ ] **Test:** Press Space (running)
- [ ] **Expected:** Live view stops, FPS shows 0.0

### Ctrl+S - Snapshot
- [ ] **Test:** Press Ctrl+S (not running)
- [ ] **Expected:** Status message: "No frame available. Start live view first."
- [ ] **Test:** Start live view, press Ctrl+S
- [ ] **Expected:** Status message: "Snapshot saved: [filename]"
- [ ] **Expected:** File created in `data/snapshots/` directory
- [ ] **Expected:** Filename format: `snapshot_YYYYMMDD_HHMMSS.png`

### Ctrl+H - Toggle Controls
- [ ] **Test:** Press Ctrl+H (controls visible)
- [ ] **Expected:** Right panel collapses, imaging area expands
- [ ] **Expected:** Status message: "Controls hidden (Ctrl+H to restore)"
- [ ] **Test:** Press Ctrl+H (controls hidden)
- [ ] **Expected:** Right panel restores to 75/25 split
- [ ] **Expected:** Status message: "Controls restored"

### Ctrl+Q - Quit
- [ ] **Test:** Press Ctrl+Q (live view running)
- [ ] **Expected:** Application closes
- [ ] **Expected:** Acquisition stops automatically
- [ ] **Expected:** Camera disconnects cleanly
- [ ] **Expected:** No error messages

### Shortcut Documentation
- [ ] Open `docs/guides/keyboard_shortcuts.md`
- [ ] **Expected:** All 4 shortcuts documented
- [ ] **Expected:** Usage tips included
- [ ] **Expected:** Validation badge present: "All shortcuts validated and working! ✅"

---

## 4. Tooltips and Help Text (Task 24)

### Camera Control Panel
- [ ] **Hover:** Exposure spin box
- [ ] **Expected:** Tooltip appears: "Fine exposure control..."
- [ ] **Expected:** Status bar shows: "Adjust exposure precisely..."

- [ ] **Hover:** Exposure slider
- [ ] **Expected:** Tooltip: "Coarse exposure adjustment..."

- [ ] **Hover:** Gain spin box
- [ ] **Expected:** Tooltip: "Sensor gain in dB. Increase only when exposure cannot be lengthened."

- [ ] **Hover:** Start Live button
- [ ] **Expected:** Tooltip mentions Space shortcut

- [ ] **Hover:** Snapshot button
- [ ] **Expected:** Tooltip mentions Ctrl+S shortcut

### White Balance Panel
- [ ] **Hover:** Preset combo box
- [ ] **Expected:** Tooltip explains "Custom" behavior

- [ ] **Hover:** Red/Green/Blue gain spin boxes
- [ ] **Expected:** Tooltip: "Manual channel gain..."

- [ ] **Hover:** Reset button
- [ ] **Expected:** Tooltip: "Restore default gains (1.0, 1.0, 1.0)."

### Focus Assistant
- [ ] **Hover:** Focus score label
- [ ] **Expected:** Tooltip: "Higher values indicate sharper edges..."

- [ ] **Hover:** Progress bar
- [ ] **Expected:** Tooltip: "Visual indicator of focus quality..."

### Live View
- [ ] **Hover:** Image display area
- [ ] **Expected:** Tooltip: "Live feed display..."

- [ ] **Hover:** Resolution/frame info label
- [ ] **Expected:** Tooltip: "Resolution and frame index..."

### Settings Manager
- [ ] **Hover:** Preset list
- [ ] **Expected:** Tooltip: "Saved presets on disk..."

- [ ] **Hover:** Name input field
- [ ] **Expected:** Tooltip: "Name used when saving/loading presets..."

- [ ] **Hover:** Load/Save/Delete buttons
- [ ] **Expected:** Tooltips present and descriptive

### Tooltip Reference
- [ ] Open `docs/guides/tooltips_reference.md`
- [ ] **Expected:** All 31 tooltips documented
- [ ] **Expected:** Table format with widget/tooltip/status tip
- [ ] **Expected:** Best practices section included

---

## 5. Documentation (Task 25)

### README.md
- [ ] Open `README.md`
- [ ] **Expected:** Status line: "Phase 6 Complete - Ready for Validation"
- [ ] **Expected:** Features list in active tense (not "Planned")
- [ ] **Expected:** All phases marked complete (0-6)
- [ ] **Expected:** Documentation section updated with new guides

### ARCHITECTURE.md
- [ ] Open `docs/architecture/ARCHITECTURE.md`
- [ ] **Expected:** Phase 6 section present
- [ ] **Expected:** All tasks marked: ✅
- [ ] **Expected:** Task 22: Error handling ✅
- [ ] **Expected:** Task 23: Keyboard shortcuts ✅
- [ ] **Expected:** Task 24: Tooltips ✅
- [ ] **Expected:** Task 25: Documentation ✅

### User Guides
- [ ] `docs/guides/keyboard_shortcuts.md` exists
- [ ] `docs/guides/troubleshooting.md` exists
- [ ] `docs/guides/tooltips_reference.md` exists

### Troubleshooting Guide
- [ ] Open `docs/guides/troubleshooting.md`
- [ ] **Expected:** "Startup Issues" section
- [ ] **Expected:** "Runtime Issues" section
- [ ] **Expected:** "GUI Issues" section
- [ ] **Expected:** "Error Messages" section
- [ ] **Expected:** Quick reference table at end

### CHANGELOG.md
- [ ] Open `CHANGELOG.md`
- [ ] **Expected:** Version 1.0.0 section
- [ ] **Expected:** All 6 development phases listed
- [ ] **Expected:** Known issues documented
- [ ] **Expected:** Future enhancements listed

### Documentation Links
- [ ] All links in README.md work (no 404s)
- [ ] All links in ARCHITECTURE.md work
- [ ] Cross-references between docs resolve correctly

---

## 6. Functional Testing

### Live View
- [ ] **Test:** Click "Start Live" button
- [ ] **Expected:** Camera feed appears in imaging area
- [ ] **Expected:** FPS counter shows 25-30
- [ ] **Expected:** Frame index increments
- [ ] **Expected:** Resolution displays: 1440x1080

### Exposure Control
- [ ] **Test:** Adjust exposure slider
- [ ] **Expected:** Spin box value updates
- [ ] **Expected:** Image brightness changes in real-time
- [ ] **Test:** Type value in spin box
- [ ] **Expected:** Slider position updates
- [ ] **Expected:** Image brightness changes

### Gain Control
- [ ] **Test:** Adjust gain spin box
- [ ] **Expected:** Image brightness increases
- [ ] **Test:** Set gain to 20dB in low light
- [ ] **Expected:** Image visible but noisy

### White Balance
- [ ] **Test:** Select "Reduce NIR" preset
- [ ] **Expected:** RGB spin boxes update
- [ ] **Expected:** Image color cast changes
- [ ] **Test:** Manually adjust Red gain
- [ ] **Expected:** Preset changes to "Custom"
- [ ] **Expected:** whiteBalanceChanged signal emitted

### Focus Assistant
- [ ] **Test:** Start live view
- [ ] **Expected:** Focus score updates every frame
- [ ] **Expected:** Progress bar shows percentage
- [ ] **Test:** Cover lens (defocus)
- [ ] **Expected:** Score drops toward zero
- [ ] **Test:** Focus on sharp edge
- [ ] **Expected:** Score increases (target: 500+)

### Snapshot Capture
- [ ] **Test:** Start live view, click Snapshot
- [ ] **Expected:** File saved in `data/snapshots/`
- [ ] **Expected:** Status message shows filename
- [ ] **Test:** Open saved PNG in image viewer
- [ ] **Expected:** 1440x1080 color image
- [ ] **Expected:** Matches current live view

### Settings Presets
- [ ] **Test:** Adjust exposure/gain, type preset name, click Save
- [ ] **Expected:** Preset appears in list
- [ ] **Expected:** Status message: "Preset '[name]' saved."
- [ ] **Test:** Change settings, click Load
- [ ] **Expected:** Controls revert to saved values
- [ ] **Expected:** Camera applies settings
- [ ] **Test:** Select preset, click Delete
- [ ] **Expected:** Preset removed from list
- [ ] **Expected:** File deleted from `data/presets/`

### GUI Layout
- [ ] **Test:** Drag splitter between image and controls
- [ ] **Expected:** Panels resize smoothly
- [ ] **Expected:** Minimum sizes respected
- [ ] **Test:** Collapse controls completely
- [ ] **Expected:** Imaging area fills entire window
- [ ] **Test:** Resize main window
- [ ] **Expected:** Image scales proportionally
- [ ] **Expected:** No distortion

---

## 7. Polish Validation

### Status Messages
- [ ] All operations show transient status messages
- [ ] Timeouts appropriate (1.5s for quick ops, 3-4s for saves)
- [ ] Error messages persistent (timeout_ms=0)

### Error Dialogs
- [ ] All critical errors show QMessageBox
- [ ] Dialog titles descriptive ("Acquisition Error", "Snapshot Error")
- [ ] Error messages user-friendly (not raw exceptions)
- [ ] Dialogs dismissible

### UI Consistency
- [ ] All buttons have consistent styling
- [ ] All spin boxes have units (ms, dB)
- [ ] All group boxes have clear titles
- [ ] No orphaned widgets

### Logging
- [ ] All operations logged at appropriate level
- [ ] Errors logged with exc_info=True
- [ ] Log files timestamped
- [ ] No sensitive data in logs

---

## 8. Edge Cases

### Camera Disconnection
- [ ] **Test:** Unplug camera during live view
- [ ] **Expected:** Acquisition error dialog
- [ ] **Expected:** Application doesn't crash
- [ ] **Expected:** Can restart application after reconnecting

### Disk Full
- [ ] **Test:** Fill disk, attempt snapshot (optional)
- [ ] **Expected:** Error dialog: "Could not save frame"
- [ ] **Expected:** Application continues running

### Invalid Preset Name
- [ ] **Test:** Use special characters in preset name
- [ ] **Expected:** Either sanitized or validation error
- [ ] **Expected:** No file system errors

### Rapid Operations
- [ ] **Test:** Rapidly press Space (start/stop)
- [ ] **Expected:** No crashes or state corruption
- [ ] **Expected:** Final state consistent with last command

### Long-Running Session
- [ ] **Test:** Run live view for 5+ minutes
- [ ] **Expected:** No memory leak (check Task Manager)
- [ ] **Expected:** FPS remains stable
- [ ] **Expected:** No degradation

---

## 9. Performance

### Frame Rate
- [ ] **Typical exposure (30ms):** 28-30 FPS
- [ ] **Short exposure (5ms):** 30 FPS (camera limited)
- [ ] **Long exposure (100ms):** ~10 FPS (expected)

### CPU Usage
- [ ] **Idle (no live view):** <5%
- [ ] **Live view 30 FPS:** 30-50% (acceptable)
- [ ] **No runaway processes:** Check Task Manager

### Memory Usage
- [ ] **Initial:** ~100MB
- [ ] **After 1000 frames:** <200MB (stable)
- [ ] **No leak:** Stops growing after initial ramp

---

## 10. Final Checks

### Git Status
- [ ] Run: `git status`
- [ ] **Expected:** No uncommitted test files
- [ ] **Expected:** New docs committed
- [ ] **Expected:** CHANGELOG.md committed

### Directory Structure
- [ ] `data/presets/` exists
- [ ] `data/snapshots/` exists
- [ ] `logs/` exists
- [ ] `docs/guides/` contains all new guides

### Documentation Completeness
- [ ] All Phase 6 deliverables documented
- [ ] README.md reflects current state
- [ ] CHANGELOG.md describes v1.0.0
- [ ] Troubleshooting guide comprehensive

---

## Validation Summary

**Total Checklist Items:** 150+

**Pass Criteria:**
- [ ] **100% of critical items** (code quality, shortcuts, tooltips, docs)
- [ ] **≥95% of functional tests**
- [ ] **≥90% of edge cases handled gracefully**

**Signature:**

```
Validated by: _______________
Date: _______________
Version: 1.0.0
Status: [ ] PASS  [ ] FAIL (see notes)
```

**Notes:**
```
[Record any failures, deviations, or observations here]





```

---

**End of Validation Checklist**
