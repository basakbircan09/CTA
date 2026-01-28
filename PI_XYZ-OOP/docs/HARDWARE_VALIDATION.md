# Hardware Validation Checklist

**Purpose:** Validate GUI functionality with real PI XYZ stages before Phase 8 rollout.

**Prerequisites:**
- Physical PI stages connected via USB
- pipython library installed
- PI drivers (GCS DLL) installed
- Hardware configuration in `PI_Control_System/config/defaults.json` matches physical setup

## Safety Features Validation

### 1. Referencing (Initialization) Requirements
**Must Have:**
- [ ] System refuses motion commands before initialization
- [ ] Initialization follows reference order: Z → X → Y (from `REFERENCE_ORDER`)
- [ ] Each axis performs FPL (Fast Reference to Positive Limit) or configured refmode
- [ ] Initialization progress shown in system log
- [ ] After initialization, position displays update with real values

**Test Procedure:**
```bash
python pi_control_system_app.py
# Click Connect (should succeed)
# Try jogging WITHOUT initialization (should fail with error message)
# Click Initialize (should see Z → X → Y sequence in log)
# Verify position display shows non-zero values after init
```

**Expected Log Output:**
```
Connecting to hardware...
Connected successfully
Initializing axes...
Referencing Z...
Referencing X...
Referencing Y...
Initialization complete - system ready
```

### 2. Travel Range Limiting
**Must Have:**
- [ ] Each axis respects `TravelRange` limits from config
- [ ] Absolute moves clamped to [min, max] range
- [ ] Relative moves that would exceed range are prevented
- [ ] Warning message shown when move is clamped/rejected

**Test Procedure:**
```python
# From defaults.json, verify your ranges (example):
# X: TravelRange(min=0.0, max=25.0)
# Y: TravelRange(min=0.0, max=25.0)
# Z: TravelRange(min=0.0, max=25.0)

# Test 1: Try to jog X beyond max range
# - Initialize system
# - Read current X position (e.g., 12.5mm)
# - Set jog step to 20mm
# - Click "+X" (should clamp to 25.0, not go to 32.5)

# Test 2: Try to jog below min range
# - Move axis close to 0.0
# - Try negative jog that would go below 0.0
# - Should clamp to 0.0 or reject move
```

**Config Verification:**
```bash
python -m PI_Control_System.config.cli show
# Verify X.range, Y.range, Z.range match physical stage limits
```

### 3. Parking Sequence
**Must Have:**
- [ ] Park position defined in config (e.g., 200.0mm)
- [ ] Park sequence moves Z first, then X/Y in parallel
- [ ] All axes reach park position before disconnect
- [ ] Park position is within travel range for all axes

**Test Procedure:**
```bash
# With system initialized and stages at random positions:
# Click Disconnect (should auto-park first)
# Observe Z moving first in log
# Then X and Y should move together
# Verify final positions match config.park_position
```

**Safety Check:**
```python
# Verify park_position is safe:
park_pos = 200.0  # from config
x_range = TravelRange(0.0, 25.0)  # your actual range

# Park position MUST be within range:
assert x_range.min <= park_pos <= x_range.max
```

## Device Configuration Principles

### 4. Per-Axis Configuration Enforcement
**Must Have:**
- [ ] Each axis uses its configured COM port
- [ ] Each axis uses its configured baud rate
- [ ] Stage model numbers match physical hardware
- [ ] Serial numbers match (if using USB connection)

**Test Procedure:**
```bash
# Verify config matches hardware:
python -m PI_Control_System.config.cli show

# Check output shows:
# controllers:
#   X:
#     port: "COM3"           # Verify this matches Device Manager
#     baud: 115200
#     serial: "0123456789"   # Verify matches stage label
#     stage: "62309260"      # Verify matches stage model
#   Y: ... (similar)
#   Z: ... (similar)
```

**Hardware Verification:**
1. Check Device Manager (Windows) or `/dev/ttyUSB*` (Linux)
2. Verify USB serial numbers: `python -c "from pipython import GCSDevice; d = GCSDevice(); print(d.EnumerateUSB())"`
3. Match config ports to physical connections

### 5. Velocity Limits
**Must Have:**
- [ ] Velocity settings respect `max_velocity` from config
- [ ] Velocity sliders capped at max_velocity
- [ ] Default velocity applied on startup
- [ ] Velocity changes reflected in actual motion speed

**Test Procedure:**
```bash
# From defaults.json, check velocity limits:
# X.max_velocity: 20.0 mm/s (example)
# X.default_velocity: 10.0 mm/s

# In GUI:
# - Verify velocity sliders max out at 20.0 mm/s
# - Verify default is 10.0 mm/s on startup
# - Change velocity to 15.0 mm/s
# - Perform jog move
# - Time the move to verify speed matches setting
```

## Manual and Automatic Control

### 6. Manual Jog Controls
**Must Have:**
- [ ] Jog step size configurable (default from config.default_step_size)
- [ ] +/- buttons work for all axes
- [ ] Position display updates during motion
- [ ] Motion can be stopped (future feature)
- [ ] Jog buttons disabled when not initialized

**Test Procedure:**
```bash
# Test each axis:
# 1. Set step size to 1.0mm
# 2. Click "+X" → verify moves +1.0mm (check position display)
# 3. Click "-X" → verify moves -1.0mm
# 4. Repeat for Y and Z
# 5. Change step size to 5.0mm and verify
```

### 7. Automatic Sequence Execution (if implemented)
**Must Have:**
- [ ] Waypoint sequence from config.default_waypoints
- [ ] Sequence executes in order
- [ ] Position display updates at each waypoint
- [ ] Sequence can be cancelled
- [ ] System parks after sequence completion

**Test Procedure:**
```bash
# If sequence feature implemented:
# - Load default waypoints from config
# - Start sequence
# - Verify each waypoint reached
# - Check system log for progress messages
```

## Test Execution Plan

### Phase 1: Static Checks (No Motion)
```bash
# 1. Verify configuration
python -m PI_Control_System.config.cli show

# 2. Check hardware enumeration
python -c "from pipython import GCSDevice; d = GCSDevice(); print(d.EnumerateUSB())"

# 3. Launch GUI (don't connect yet)
python pi_control_system_app.py

# 4. Verify UI elements present:
#    - Connection panel
#    - Position display (showing ---)
#    - Velocity controls (disabled)
#    - Jog buttons (disabled)
#    - System log (empty)
```

### Phase 2: Connection and Initialization
```bash
# 1. Click Connect
# Expected: Status shows "Connecting..." then "Connected"
# Expected: Log shows connection messages
# Expected: Initialize button becomes enabled

# 2. Try jogging WITHOUT initialization
# Expected: Error message OR buttons still disabled

# 3. Click Initialize
# Expected: Status shows "Initializing..." then "Ready"
# Expected: Log shows Z → X → Y sequence
# Expected: Position display shows real values (not ---)
# Expected: Jog and velocity controls become enabled
```

### Phase 3: Manual Control Testing
```bash
# Test each axis systematically:

# X-axis:
# - Note starting position
# - Set jog step to 1.0mm
# - Click "+X" five times → position should increase by 5.0mm
# - Click "-X" five times → position should return to start
# - Set jog step to 5.0mm
# - Click "+X" → position should increase by 5.0mm

# Repeat for Y-axis and Z-axis
```

### Phase 4: Safety Limit Testing
```bash
# Test 1: Upper range limit
# - Move X close to max range (e.g., 23.0mm if max is 25.0mm)
# - Try to jog +10mm
# - Verify position clamps to 25.0mm, not 33.0mm
# - Check log for warning message

# Test 2: Lower range limit
# - Move X close to min range (e.g., 2.0mm if min is 0.0mm)
# - Try to jog -5mm
# - Verify position clamps to 0.0mm
# - Check log for warning

# Repeat for Y and Z axes
```

### Phase 5: Velocity Control Testing
```bash
# Test 1: Verify velocity limits
# - Check velocity sliders max at config.max_velocity
# - Try to set higher value in spinbox (should clamp)

# Test 2: Verify velocity affects motion
# - Set X velocity to 5.0 mm/s
# - Jog +10mm, time the motion (~2 seconds expected)
# - Set X velocity to 20.0 mm/s
# - Jog +10mm, time the motion (~0.5 seconds expected)
```

### Phase 6: Park and Disconnect
```bash
# Test parking sequence:
# - With stages at random positions
# - Click Disconnect
# - Observe log: Z should park first
# - Then X and Y park together
# - Verify all axes at config.park_position
# - Status should show "Disconnected"
# - Controls should be disabled
```

## Success Criteria

All checks must pass:
- ✓ No motion possible before initialization
- ✓ Initialization follows Z → X → Y order
- ✓ Travel ranges enforced for all axes
- ✓ Park sequence executes safely (Z first)
- ✓ Velocity limits respected
- ✓ Position display updates in real-time
- ✓ Configuration matches physical hardware
- ✓ System log shows all events
- ✓ No crashes or unhandled exceptions

## Failure Response

If any test fails:
1. Document the failure in GitHub issue tracker
2. Check logs in system log widget
3. Check console output for Python exceptions
4. Verify configuration: `python -m PI_Control_System.config.cli show`
5. Test with legacy GUI to isolate hardware vs. software issue
6. Fix in new GUI, re-test, compare behavior with legacy

## Sign-off

- [ ] All Phase 1-6 tests completed
- [ ] All safety features validated
- [ ] Configuration verified correct
- [ ] No unexpected behavior observed
- [ ] Ready for operator dry run (Phase 8)

**Tested by:** _________________
**Date:** _________________
**Hardware Serial Numbers:** _________________
**Notes:** _________________
