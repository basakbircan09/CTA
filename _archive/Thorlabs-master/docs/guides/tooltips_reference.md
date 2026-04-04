# UI Help Text Reference

Complete reference for all tooltips and status bar messages in the application.

**Purpose**: Maintainability guide for developers updating UI help text.

---

## Camera Control Panel

### Exposure Controls

| Widget | Tooltip | Status Tip |
|--------|---------|-----------|
| **Exposure Spin Box** | "Fine exposure control (ms). Adjust for brightness; slider offers coarse changes." | "Adjust exposure precisely in milliseconds." |
| **Exposure Slider** | "Coarse exposure adjustment. Range matches the spin box (0.1–1000 ms)." | "Drag for quick exposure changes." |
| **Gain Spin Box** | "Sensor gain in dB. Increase only when exposure cannot be lengthened." | "Modify analog gain; higher values add noise." |

### Action Buttons

| Button | Tooltip | Status Tip |
|--------|---------|-----------|
| **Start Live** | "Begin live acquisition (Space). Applies current exposure/gain." | "Start the live camera stream." |
| **Stop** | "Stop live acquisition (Space)." | "Stop the live camera stream." |
| **Snapshot** | "Capture and save the latest frame (Ctrl+S)." | "Save the most recent frame to disk." |

---

## White Balance Panel

| Widget | Tooltip | Status Tip |
|--------|---------|-----------|
| **Preset Combo** | "Select a preset RGB gain combination. 'Custom' reflects manual adjustments." | "Choose a white balance preset for the current scene." |
| **Red Gain** | "Manual channel gain. Increase to boost the channel, decrease to reduce it." | "Adjust individual RGB gains for manual white balance tuning." |
| **Green Gain** | "Manual channel gain. Increase to boost the channel, decrease to reduce it." | "Adjust individual RGB gains for manual white balance tuning." |
| **Blue Gain** | "Manual channel gain. Increase to boost the channel, decrease to reduce it." | "Adjust individual RGB gains for manual white balance tuning." |
| **Reset Button** | "Restore default gains (1.0, 1.0, 1.0)." | "Reset white balance to factory defaults." |

**Available Presets:**
- **Default**: (1.0, 1.0, 1.0) - Factory settings
- **Reduce NIR**: (0.6, 0.8, 1.0) - Mild NIR compensation
- **Strong NIR**: (0.4, 0.7, 1.0) - Heavy NIR compensation for skin tones
- **Warm**: (1.0, 0.9, 0.7) - Warmer color temperature
- **Cool**: (0.9, 1.0, 1.2) - Cooler color temperature
- **Custom**: Reflects manual RGB adjustments

---

## Focus Assistant

| Widget | Tooltip | Status Tip |
|--------|---------|-----------|
| **Focus Label** | "Higher values indicate sharper edges. Aim for the highest score while focusing." | N/A |
| **Progress Bar** | "Visual indicator of focus quality. 100% corresponds to the best recent score." | N/A |
| **Widget Container** | "Monitor focus quality while adjusting the lens." | N/A |

**Score Interpretation:**
- 0-200: Very blurry
- 200-500: Slightly out of focus
- 500-800: Good focus
- 800+: Sharp focus

---

## Settings Manager

| Widget | Tooltip | Status Tip |
|--------|---------|-----------|
| **Preset List** | "Saved presets on disk. Select to load, delete, or overwrite." | N/A |
| **Name Input** | "Name used when saving/loading presets. Accepts alphanumeric characters." | N/A |
| **Load Button** | "Load the selected or typed preset from disk." | N/A |
| **Save Button** | "Save current camera settings under the typed name." | N/A |
| **Delete Button** | "Delete the selected preset file." | N/A |
| **Refresh Button** | "Re-scan the presets directory for new files." | N/A |

---

## Live View

| Widget | Tooltip | Status Tip |
|--------|---------|-----------|
| **Image Label** | "Live feed display. Start the camera to view frames; image scales to available space." | N/A |
| **Info Label** | "Resolution and frame index of the most recent image." | N/A |
| **Widget Container** | "Displays the current camera image and metadata." | N/A |

---

## Keyboard Shortcuts

See [keyboard_shortcuts.md](keyboard_shortcuts.md) for complete keyboard shortcut documentation.

**Shortcuts mentioned in tooltips:**
- **Space**: Toggle Start/Stop (mentioned in Start/Stop buttons)
- **Ctrl+S**: Capture Snapshot (mentioned in Snapshot button)
- **Ctrl+H**: Toggle Controls Panel (documented separately)
- **Ctrl+Q**: Quit Application (documented separately)

---

## Best Practices for Help Text

### Writing Tooltips
1. **Be concise**: 1-2 sentences maximum
2. **Explain purpose**: What does this control do?
3. **Provide context**: When should the user adjust this?
4. **Include shortcuts**: Reference keyboard shortcuts where relevant
5. **Use active voice**: "Adjust exposure" not "Exposure is adjusted"

### Writing Status Tips
1. **Action-oriented**: Describe what will happen
2. **Shorter than tooltips**: Single sentence
3. **No redundancy**: Different information than tooltip
4. **Present tense**: "Start the live camera stream"

### Consistency Guidelines
- **Units**: Always include units (ms, dB, px)
- **Ranges**: Mention valid ranges when helpful
- **Warnings**: Include side effects ("higher values add noise")
- **Workflow hints**: Guide best practices ("only when exposure cannot be lengthened")

---

## Maintenance Notes

**Adding new tooltips:**
```python
widget.setToolTip("Concise explanation of purpose and usage.")
widget.setStatusTip("Action-oriented description.")
```

**Testing tooltips:**
1. Hover over widget for 1 second
2. Verify tooltip appears with correct text
3. Check status bar for status tip
4. Test on Windows/macOS/Linux if available

**Updating this document:**
- When adding new widgets, update this reference
- When changing help text, update this document
- Keep examples consistent with code
- Maintain alphabetical order within sections
