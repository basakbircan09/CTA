"""
Test Thorlabs Camera Connection
Simple script to verify camera SDK is working and camera is detected
"""

import os
import sys

# Fix Windows console encoding
if sys.platform == 'win32':
    import codecs
    sys.stdout = codecs.getwriter('utf-8')(sys.stdout.buffer, 'strict')
    sys.stderr = codecs.getwriter('utf-8')(sys.stderr.buffer, 'strict')

# Add DLL path to system PATH
dll_path = os.path.join(os.path.dirname(__file__), "..", "vendor", "thorlabs_sdk", "dlls", "64_lib")
os.environ['PATH'] = dll_path + os.pathsep + os.environ['PATH']

# For Python 3.8+, explicitly add DLL directory
if hasattr(os, 'add_dll_directory'):
    os.add_dll_directory(dll_path)

try:
    from thorlabs_tsi_sdk.tl_camera import TLCameraSDK

    print("=" * 60)
    print("Thorlabs Camera Connection Test")
    print("=" * 60)

    # Initialize SDK
    with TLCameraSDK() as sdk:
        print("\n[OK] Camera SDK initialized successfully")

        # Discover cameras
        available_cameras = sdk.discover_available_cameras()
        print(f"\n[OK] Found {len(available_cameras)} camera(s)")

        if len(available_cameras) == 0:
            print("\n[ERROR] No cameras detected!")
            print("  - Check USB connection")
            print("  - Verify camera power")
            print("  - Check ThorCam software can see camera")
            sys.exit(1)

        # Display camera information
        for i, serial in enumerate(available_cameras):
            print(f"\n  Camera {i+1}: {serial}")

        # Open first camera
        print(f"\n[OK] Opening camera: {available_cameras[0]}")
        with sdk.open_camera(available_cameras[0]) as camera:
            print(f"  - Model: {camera.model}")
            print(f"  - Name: {camera.name}")
            print(f"  - Sensor Type: {camera.camera_sensor_type}")
            print(f"  - Sensor Size: {camera.sensor_width_pixels} x {camera.sensor_height_pixels}")
            print(f"  - Bit Depth: {camera.bit_depth}")
            print(f"  - Firmware: {camera.firmware_version}")
            print(f"  - Communication: {camera.communication_interface}")
            print(f"  - USB Port Type: {camera.usb_port_type}")

            # Check if color camera
            from thorlabs_tsi_sdk.tl_camera_enums import SENSOR_TYPE
            if camera.camera_sensor_type == SENSOR_TYPE.BAYER:
                print(f"  - Color Filter Phase: {camera.color_filter_array_phase}")
                print("\n[OK] This is a COLOR camera (requires color processing)")
            else:
                print("\n  This is a MONOCHROME camera")

    print("\n" + "=" * 60)
    print("[SUCCESS] All tests passed! Camera is ready for use.")
    print("=" * 60)

except ImportError as e:
    print(f"\n[ERROR] Failed to import thorlabs_tsi_sdk: {e}")
    print("\nPlease install the SDK package:")
    print("  pip install thorlabs_tsi_camera_python_sdk_package.zip")
    sys.exit(1)

except Exception as e:
    print(f"\n[ERROR] Error: {e}")
    print("\nTroubleshooting:")
    print("  - Ensure DLLs are in Python Toolkit/dlls/64_lib/")
    print("  - Check camera is connected via USB")
    print("  - Verify ThorCam software works")
    sys.exit(1)
