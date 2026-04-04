# Hardware Validation Quick Start

**Before you begin:**
1. Connect PI stages via USB
2. Verify Device Manager shows COM ports
3. Check config: `python -m PI_Control_System.config.cli show`

## Launch Application

```bash
# Option 1: Real hardware
python pi_control_system_app.py

# Option 2: Legacy comparison
python pi_control_system_app.py --legacy
```

## Critical Safety Tests (15 minutes)

### Test 1: Initialization Order (2 min)
```
1. Click Connect
2. Click Initialize
3. Watch log for: Z → X → Y sequence
✓ PASS: All three axes initialized in correct order
✗ FAIL: Wrong order or any axis skipped
```

### Test 2: Pre-Init Motion Block (1 min)
```
1. Click Connect (don't initialize)
2. Try to jog any axis
✓ PASS: Motion blocked, error shown
✗ FAIL: Stage moved without initialization
```

### Test 3: Range Limits (5 min)
```
For each axis:
1. Initialize system
2. Check config range (e.g., X: 0.0 to 25.0mm)
3. Move close to max (e.g., 23.0mm)
4. Jog +10mm
5. Verify position ≤ max (25.0mm), not unclamped

✓ PASS: Position clamped to configured max
✗ FAIL: Position exceeded range
```

### Test 4: Park Sequence (3 min)
```
1. Move axes to random positions
2. Click Disconnect
3. Watch log: Z parks first, then X/Y together
4. Verify all axes at park position (e.g., 200.0mm)

✓ PASS: Z-first sequence, all parked correctly
✗ FAIL: Wrong order OR park position incorrect
```

### Test 5: Velocity Enforcement (4 min)
```
1. Check config max_velocity (e.g., 20.0 mm/s)
2. Try to set velocity slider above max
3. Verify slider/spinbox clamped to max

✓ PASS: Cannot exceed max velocity
✗ FAIL: Allowed to set >max velocity
```

## If Any Test Fails

**STOP. Do not proceed to Phase 8.**

1. Document failure in issue tracker
2. Compare with legacy GUI behavior
3. Check configuration vs. hardware mismatch
4. Review logs: system log widget + console output
5. Fix and re-test

## After All Tests Pass

Mark sign-off in `docs/HARDWARE_VALIDATION.md` and proceed to Phase 8 operator dry run.

## Quick Config Check

```bash
# Show current config
python -m PI_Control_System.config.cli show

# Key values to verify:
# - reference_order: [Z, X, Y]
# - park_position: <within all axis ranges>
# - X/Y/Z ranges: match physical stage limits
# - X/Y/Z max_velocity: safe for your stages
```

## Emergency Stop

If anything goes wrong during testing:
1. Close GUI immediately (X button)
2. Power off stages if needed
3. Check `PI_Control_System/config/defaults.json` for configuration errors
4. Consult `docs/HARDWARE_VALIDATION.md` for detailed procedures
