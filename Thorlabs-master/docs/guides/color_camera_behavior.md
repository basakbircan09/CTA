# CS165CU Color Camera Behavior - Explanation

## What You're Observing

### Your Observation:
> "It looks like thermal imaging - doesn't show real world color of objects like my hand, but in gradient colors with high saturation. But surprisingly PC screens look fine!"

**This is NORMAL and expected!** Let me explain why.

---

## The Problem: Near-Infrared (NIR) Sensitivity

### Scientific Cameras vs Consumer Cameras

**Consumer cameras** (phone, webcam):
- Have **IR cut filter** (blocks 700-1100nm)
- Only sensitive to visible light (400-700nm)
- Show "natural" human-perceived colors

**Scientific cameras** (CS165CU):
- **NO IR cut filter** (for maximum sensitivity)
- Sensitive to 350-1100nm (includes NIR!)
- Show "unnatural" colors because of IR contamination

---

## Why Your Hand Looks Weird

### Human Skin Spectral Properties

Your hand emits/reflects:
1. **Visible light** (400-700nm): Normal skin tones
2. **Near-infrared** (700-1100nm): STRONG reflection (~50-60% reflectance)

The CS165CU sees BOTH, which causes:
- Red channel: Gets visible red + NIR → **oversaturated**
- Green channel: Gets visible green + some NIR → skewed
- Blue channel: Gets visible blue + minimal NIR → relatively normal

**Result**: Skin looks pinkish-red or magenta with high saturation

### Why PC Screens Look Normal

**LCD/LED screens**:
- Emit pure visible light (RGB phosphors: ~450nm, ~550nm, ~630nm)
- **Very little NIR emission** (<5%)
- The camera sees mostly visible light → accurate colors!

**This is why:**
- ✅ Screens: Natural colors
- ❌ Skin/fabric/wood: Weird colors (NIR contamination)
- ❌ Plants: Look very bright (chlorophyll reflects NIR strongly!)

---

## Technical Explanation

### Bayer Filter Response

CS165CU has Bayer color filter:
```
Pattern:    R  G₁ | B  G₂
           --------+-------
Spectral:
  R:  600-700nm (visible) + 700-1100nm (NIR) ← PROBLEM!
  G:  500-600nm (visible) + some NIR
  B:  400-500nm (visible) + minimal NIR
```

**Without IR cut filter**:
- Red pixels get ~2x more light than they should (visible + NIR)
- Color balance completely wrong for natural scenes
- Fine for emissive screens (no NIR)

---

## Solutions

### Option 1: Hardware IR Cut Filter (Recommended for Natural Color)

**What**: Physical filter that blocks 700-1100nm
**Where**: Mounts in front of camera lens
**Cost**: $10-50 depending on size

**Thorlabs options**:
- FEL0700 (700nm longpass - blocks IR, passes visible)
- Or any standard photography IR cut filter (52mm, 58mm, etc.)

**Result**:
- ✅ Natural skin tones
- ✅ Accurate colors for all objects
- ❌ Lower sensitivity (blocks ~50% of light)
- ❌ Reduces scientific utility (loses NIR data)

### Option 2: Software White Balance Adjustment

**What**: Adjust RGB gain ratios to compensate
**Limitation**: Can't fully fix it (IR is mixed into color channels)

**Partial improvement**:
```python
# Reduce red channel gain
cam.set_color_format("rgb")
# Then manually adjust gains (if PyLabLib exposes this)
red_gain = 0.6    # Reduce red (has most NIR)
green_gain = 0.8  # Slightly reduce green
blue_gain = 1.0   # Keep blue normal
```

**Result**:
- 🟡 Slight improvement
- ❌ Can't fully correct (data is contaminated)
- ❌ Loses dynamic range

### Option 3: Accept Scientific Camera Behavior

**For scientific applications**:
- Keep NIR sensitivity (useful for many experiments!)
- Use camera for measurement, not "pretty pictures"
- Add IR filter only when natural color needed

**Advantages**:
- ✅ Maximum sensitivity
- ✅ See NIR information (useful for materials, biology, etc.)
- ✅ No light loss
- ✅ True scientific imaging

---

## Comparison Images (What You'd See)

### Without IR Filter (Current):
```
Human hand:      Pink/magenta, oversaturated, looks "thermal"
Green plants:    Bright white/pink (NIR reflectance)
Blue jeans:      Purple-ish (NIR reflection)
PC screen:       NORMAL ✓ (no NIR emission)
LED lights:      NORMAL ✓ (no NIR emission)
```

### With IR Cut Filter:
```
Human hand:      Normal skin tone ✓
Green plants:    Normal green ✓
Blue jeans:      Normal blue ✓
PC screen:       NORMAL ✓
LED lights:      NORMAL ✓

BUT: Lower sensitivity, ~50% light loss
```

---

## Why This Happens in Scientific Cameras

### Design Philosophy

**Consumer cameras** (phone, DSLR):
- Goal: Pretty pictures that look natural
- Solution: IR cut filter standard
- Trade-off: Lower sensitivity, no NIR data

**Scientific cameras** (CS165CU, research grade):
- Goal: Maximum information capture
- Solution: No filters, wide spectral range
- Trade-off: Colors don't look "natural" to humans

### Your CS165CU Spectral Response

According to Thorlabs specs:
```
Spectral Range: 350-1100nm
Peak QE: ~55% at 550nm (green)
NIR Response: Still 30-40% at 800-900nm

This means:
- Visible light (400-700nm): Strong response
- NIR light (700-1100nm): Still significant response!
```

**For comparison**, human eye:
```
Spectral Range: 380-750nm
NIR Response: 0% (we can't see it at all)
```

---

## Real-World Examples

### Materials with High NIR Reflectance:
1. **Human skin**: 50-60% NIR reflectance (looks pink/red)
2. **Green plants**: 40-50% NIR reflectance (looks bright/white)
3. **Some fabrics**: Variable NIR (weird colors)
4. **Wood**: High NIR (looks reddish)

### Materials with Low NIR:
1. **LCD/LED screens**: <5% NIR (looks normal!)
2. **Pure pigments**: Minimal NIR (looks normal)
3. **Water**: Low NIR (looks normal)

---

## Recommendations for Your Project

### For General-Purpose Imaging (Natural Colors):

**Hardware solution** (best):
```
Buy: IR cut filter (52mm or appropriate diameter)
Mount: In front of camera lens
Result: Natural colors, but ~50% light loss
Cost: $15-30 on Amazon
```

Example search terms:
- "52mm IR cut filter"
- "Infrared cut filter photography"
- "Hot mirror filter" (another name)

### For Scientific Imaging (Keep Current):

**No filter needed**:
- Accept the color cast
- Use camera for quantitative measurements
- NIR sensitivity is actually USEFUL for:
  - Material identification
  - Biological imaging (blood flow, tissue)
  - Quality control (see defects invisible to eye)
  - Multispectral analysis

### For Software Development:

**Use PC screen as test target**:
- Screens emit clean RGB (no NIR)
- Good for testing exposure, ROI, capture, etc.
- Colors will look correct
- Perfect for GUI development phase

---

## Modified Demo with Better Color Display

I can create an improved version that:
1. Applies color correction (reduces red channel)
2. Adds white balance presets
3. Shows histogram for adjustment
4. Saves RAW + corrected images

**But**: Software can't fully fix hardware issue (NIR mixed into RGB data)

---

## The Bottom Line

### Your Observation is Correct ✓

> "Looks like thermal imaging for hand, but screens look fine"

**Explanation**:
- Hand reflects IR → red channel oversaturated → weird colors
- Screen emits no IR → all channels balanced → normal colors

### This is NOT a Bug, It's a Feature!

Scientific cameras are designed this way for:
- Maximum light sensitivity
- Full spectral coverage
- Scientific measurements

### Quick Fixes:

**Immediate** (software, partial):
- Adjust color balance in software
- Use for screen imaging (works fine!)
- Accept scientific camera behavior

**Proper** (hardware, complete):
- Buy IR cut filter (~$20)
- Mount in front of lens
- Get natural colors

---

## Would You Like Me To:

1. ✅ Create improved demo with color correction controls?
2. ✅ Add white balance presets (daylight, tungsten, custom)?
3. ✅ Show you how to work with raw Bayer data for scientific use?
4. ✅ Recommend specific IR cut filter models?

**For now**: Your camera is working perfectly! The "weird colors" are because you're seeing NIR light that your eyes can't see. Screens look normal because they don't emit NIR.

---

**This is actually COOL - you're seeing part of the light spectrum that humans can't see! 🌈➡️📸**
