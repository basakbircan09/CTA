# PI Stage Control GUI - Production Version

**Production-ready GUI for controlling Physik Instrumente 3-axis XYZ stage system**

This application integrates the proven hardware control logic from `Tmotion2.0.py` with a modern, user-friendly graphical interface built with PySide6.

## Features

### Hardware Control
- ✅ **Real hardware connection** via USB to three independent PI controllers
- ✅ **Safe initialization sequence** with Z-first referencing (prevents collisions)
- ✅ **Position safety clamping** to prevent out-of-bounds movements
- ✅ **Real-time position monitoring** using `qPOS()` commands (10 Hz update rate)
- ✅ **Velocity control** per axis with configurable limits
- ✅ **Emergency stop** functionality

### Control Modes

#### 1. Manual Control Mode
- Relative movements using `MVR()` commands
- Adjustable step size (0.1 - 50 mm)
- Independent +/- buttons for each axis
- Immediate feedback and position display

#### 2. Automated Sequence Mode
- Multi-waypoint sequential movement using `MOV()` commands
- Configurable hold time at each waypoint
- Easy waypoint addition/removal via table interface
- Real-time sequence progress tracking

### Safety Features
- Position clamping to safe travel ranges (from `origintools.safe_range()`)
- User confirmation prompts before initialization and motion
- Safe parking sequence (Z moves first, then X/Y simultaneously)
- Visual status indicators for connection state
- System log for all operations

## System Requirements

### Hardware
- 3× Physik Instrumente controllers (VT-80 stages, model 62309260)
- USB connections configured as:
  - X-axis: Serial# 025550131 (COM5)
  - Y-axis: Serial# 025550143 (COM3)
  - Z-axis: Serial# 025550149 (COM4)

### Software
- Python 3.8+
- Required packages:
  - `PySide6` (Qt6 GUI framework)
  - `pipython` (PI GCS command library)

## Installation

1. **Navigate to the GUI folder:**
   ```bash
   cd PI_Control_GUI
   ```

2. **Install required packages:**
   ```bash
   pip install PySide6 pipython
   ```

## Usage

### Starting the Application

```bash
python main_gui.py
```

### Connection & Initialization Workflow

1. **Connect Controllers**
   - Click "Connect Controllers" button
   - System will connect to all three controllers via USB
   - Status indicator will turn green when connected

2. **Initialize & Reference**
   - Click "Initialize & Reference" button
   - **WARNING:** Stages will move during referencing!
   - Confirm the safety prompt
   - Stages will reference in safe order: Z → X → Y
   - Wait for completion (status indicator turns cyan)

3. **Ready for Operation**
   - System is now ready for manual or automated control

### Manual Control Mode

1. Select "Manual Control" mode
2. Set desired step size (mm)
3. Adjust velocities for each axis (optional)
4. Click +/- buttons to move axes incrementally
5. Monitor real-time positions in the display

### Automated Sequence Mode

1. Select "Automated Sequence" mode
2. Configure waypoints:
   - Edit existing waypoints in the table
   - Add new waypoints with "+ Add Waypoint"
   - Remove waypoints with "Remove" button
   - Set hold time at each waypoint
3. Click "▶ Start Sequence" to begin
4. Monitor progress in status display
5. Use "⏹ Stop Motion" for emergency stop

### Parking the System

- Click "Park All Axes" in either mode
- Confirms move to default park position (200 mm)
- Uses safe sequence: Z first, then X/Y together

### Shutdown

1. Click "Disconnect" button, or
2. Close the window (will prompt for confirmation if connected)

## Configuration

Edit `config.py` to customize:

### Hardware Parameters
```python
CONTROLLER_CONFIG = {
    'X': {
        'serialnum': '025550131',  # USB serial number
        'stage': '62309260',        # Stage model
        'refmode': 'FPL',          # Reference mode
        # ...
    },
    # Y and Z configurations...
}
```

### Motion Parameters
```python
DEFAULT_VELOCITY = 10.0    # Default velocity (mm/s)
MAX_VELOCITY = 20.0        # Maximum allowed velocity (mm/s)
DEFAULT_PARK_POSITION = 200.0  # Park position (mm)
```

### Safe Travel Ranges
```python
AXIS_TRAVEL_RANGES = {
    'X': {'min': 5.0, 'max': 200.0},
    'Y': {'min': 0.0, 'max': 200.0},
    'Z': {'min': 15.0, 'max': 200.0},
}
```

### GUI Settings
```python
DEFAULT_STEP_SIZE = 1.0           # Default manual step size (mm)
POSITION_UPDATE_INTERVAL = 100    # Position refresh rate (ms)
```

## Architecture

### File Structure
```
PI_Control_GUI/
├── main_gui.py              # Main GUI application
├── hardware_controller.py   # Hardware interface layer
├── config.py                # Configuration parameters
└── README.md                # This file
```

### Module Descriptions

#### `main_gui.py`
- PySide6-based graphical interface
- User interaction handling
- Real-time display updates
- Thread management for long operations

#### `hardware_controller.py`
- `PIHardwareController` class
- Direct hardware communication via pipython
- Implements all GCS commands (MOV, MVR, VEL, qPOS, etc.)
- Safety checks and error handling
- Based on validated logic from `Tmotion2.0.py`

#### `config.py`
- Centralized configuration
- Hardware-specific parameters
- Motion limits and defaults
- GUI styling parameters

### Dependencies on Original Scripts

This application **does not modify** any existing scripts. It uses:
- `origintools.py` - Imports `safe_range()` function
- Hardware parameters from `Tmotion2.0.py` (copied to `config.py`)
- Initialization sequence logic from `Tmotion2.0.py`

## Safety Notes

⚠️ **IMPORTANT SAFETY INFORMATION**

1. **Initialization causes motion**: The reference sequence will move all stages to their limit switches
2. **Clear workspace**: Ensure nothing obstructs the stage motion before initializing
3. **Emergency stop**: Use "⏹ Stop Motion" or "Disconnect" in emergencies
4. **Position limits**: All movements are automatically clamped to safe ranges
5. **Z-axis priority**: Z always moves first during parking to prevent collisions
6. **User confirmation**: Critical operations require confirmation prompts

## Troubleshooting

### Connection Issues
- **Problem:** "Connection failed" error
- **Solutions:**
  - Verify USB cables are connected
  - Check COM port assignments match configuration
  - Ensure no other software is using the controllers
  - Verify serial numbers in `config.py`

### Initialization Issues
- **Problem:** Initialization fails or times out
- **Solutions:**
  - Ensure stages are not mechanically blocked
  - Check that limit switches are functional
  - Verify stage model in configuration matches hardware
  - Review system log for specific error messages

### Position Not Updating
- **Problem:** Position display shows 0.000 or doesn't update
- **Solutions:**
  - Ensure initialization completed successfully
  - Check "System Log" for communication errors
  - Verify controllers are still connected

### Motion Not Executing
- **Problem:** Commands issued but stages don't move
- **Solutions:**
  - Verify system is initialized (status shows "Ready")
  - Check servo is enabled for all axes
  - Ensure requested position is within safe range
  - Review velocity settings (not zero)

## System Log

The **System Log** panel at the bottom-left shows:
- Connection status messages
- Initialization progress
- Motion commands executed
- Position updates
- Error messages with descriptions

Use this log to diagnose issues and track system operations.

## Example Workflow

### Quick Start for Testing
1. Launch application: `python main_gui.py`
2. Click "Connect Controllers"
3. Click "Initialize & Reference" (confirm prompt)
4. Switch to "Manual Control"
5. Set step size to 5 mm
6. Test each axis with +/- buttons
7. Monitor positions in real-time display
8. Click "Park All Axes" when done
9. Click "Disconnect"

### Running an Automated Sequence
1. Complete connection and initialization
2. Switch to "Automated Sequence" mode
3. Edit waypoint table:
   - Waypoint 1: X=10, Y=5, Z=20, Hold=1s
   - Waypoint 2: X=25, Y=15, Z=30, Hold=2s
4. Click "▶ Start Sequence"
5. Watch status updates
6. Sequence completes automatically
7. Click "Park All Axes"

## Version History

- **v1.0** - Initial production release
  - Full hardware integration from Tmotion2.0.py
  - Manual and automated control modes
  - Real-time position monitoring
  - Safety features and error handling
  - Modern PySide6 interface

## Support

For issues or questions:
1. Check the **System Log** for error messages
2. Review this README troubleshooting section
3. Verify configuration in `config.py`
4. Consult original `Tmotion2.0.py` for hardware reference

## License

Based on original PI example code:
- (c)2024 Physik Instrumente (PI) SE & Co. KG
- Provided for demonstration and operational purposes
