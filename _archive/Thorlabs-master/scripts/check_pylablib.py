"""
Test PyLabLib with Thorlabs CS165CU Camera
Verify compatibility with current DLL set
"""

import sys
import os

# Fix Windows console encoding
if sys.platform == 'win32':
    import codecs
    sys.stdout = codecs.getwriter('utf-8')(sys.stdout.buffer, 'strict')
    sys.stderr = codecs.getwriter('utf-8')(sys.stderr.buffer, 'strict')

print("=" * 70)
print("PyLabLib + Thorlabs CS165CU Camera Test")
print("=" * 70)

# Point pylablib to our ThorCam DLLs
import pylablib as pll
thorcam_dll_path = os.path.join(os.path.dirname(__file__), "..", "vendor", "thorcam")
pll.par["devices/dlls/thorlabs_tlcam"] = thorcam_dll_path
print(f"\n[CONFIG] DLL path: {thorcam_dll_path}")

try:
    from pylablib.devices import Thorlabs

    # Test 1: List cameras
    print("\n[TEST 1] Discovering cameras...")
    cameras = Thorlabs.list_cameras_tlcam()
    print(f"[OK] Found {len(cameras)} camera(s): {cameras}")

    if len(cameras) == 0:
        print("\n[ERROR] No cameras detected!")
        sys.exit(1)

    # Test 2: Open camera
    print(f"\n[TEST 2] Opening camera {cameras[0]}...")
    cam = Thorlabs.ThorlabsTLCamera(serial=cameras[0])
    print("[OK] Camera opened successfully")

    # Test 3: Get camera info
    print("\n[TEST 3] Querying camera properties...")
    device_info = cam.get_device_info()  # (model, name, serial, firmware)
    detector_size = cam.get_detector_size()  # (width, height)
    sensor_info = cam.get_sensor_info()  # sensor details
    roi = cam.get_roi()  # (hstart, hend, vstart, vend, hbin, vbin)
    current_exposure = cam.get_exposure()  # current exposure in seconds
    gain_range = cam.get_gain_range()  # (min, max) in dB

    print(f"  Model: {device_info[0]}")
    print(f"  Name: {device_info[1]}")
    print(f"  Serial: {device_info[2]}")
    print(f"  Firmware: {device_info[3]}")
    print(f"  Detector Size: {detector_size[0]} x {detector_size[1]} pixels")
    print(f"  Sensor Info: {sensor_info}")
    print(f"  Current Exposure: {current_exposure:.6f} sec")
    print(f"  Gain Range: {gain_range[0]:.1f} - {gain_range[1]:.1f} dB")
    print(f"  Current ROI: hstart={roi[0]}, hend={roi[1]}, vstart={roi[2]}, vend={roi[3]}, hbin={roi[4]}, vbin={roi[5]}")

    # Test 4: Check if color camera
    print("\n[TEST 4] Checking camera type...")
    # PyLabLib doesn't directly expose sensor type, but we can test color format
    try:
        # Try to set color format - only works on color cameras
        current_format = cam.get_color_format()
        print(f"[OK] This is a COLOR camera")
        print(f"  Current color format: {current_format}")

        # Show available formats
        print("  Testing color format options...")
        cam.set_color_format("rgb24")  # 24-bit RGB
        print("    - rgb24: OK")
        cam.set_color_format("rgb48")  # 48-bit RGB
        print("    - rgb48: OK")
        cam.set_color_format(current_format)  # Restore
        print(f"  Restored to: {current_format}")
    except Exception as e:
        print(f"[INFO] Color format not available - monochrome camera? ({e})")

    # Test 5: Capture a test frame
    print("\n[TEST 5] Capturing test frame...")
    cam.set_exposure(0.05)  # 50ms
    print(f"  Set exposure: 50ms")

    cam.start_acquisition()
    print("  Acquisition started")

    frame = cam.snap()
    print(f"[OK] Frame captured!")
    print(f"  Shape: {frame.shape}")
    print(f"  Dtype: {frame.dtype}")
    print(f"  Range: {frame.min()} - {frame.max()}")

    # Check if RGB or grayscale
    if frame.ndim == 3:
        print(f"  Color channels: {frame.shape[2]} (RGB)")
    else:
        print(f"  Grayscale image")

    cam.stop_acquisition()
    print("  Acquisition stopped")

    # Test 6: Cleanup
    print("\n[TEST 6] Closing camera...")
    cam.close()
    print("[OK] Camera closed successfully")

    print("\n" + "=" * 70)
    print("[SUCCESS] All PyLabLib tests passed!")
    print("=" * 70)
    print("\nConclusions:")
    print("  - PyLabLib works with current DLL set")
    print("  - Camera detected and controllable")
    print("  - Frame acquisition functional")
    print("  - Color processing automatic (if color camera)")
    print("\nPyLabLib is READY for your application.")

except ImportError as e:
    print(f"\n[ERROR] Failed to import PyLabLib: {e}")
    print("\nTroubleshooting:")
    print("  - Ensure pylablib is installed: pip install pylablib")
    sys.exit(1)

except Exception as e:
    print(f"\n[ERROR] Test failed: {e}")
    import traceback
    traceback.print_exc()
    print("\nTroubleshooting:")
    print("  - Check DLL path is correct")
    print("  - Verify camera is connected")
    print("  - Ensure ThorCam software works")
    sys.exit(1)
