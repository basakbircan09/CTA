import os
import sys
from pathlib import Path

# Set up DLL path BEFORE importing pipython
PROJECT_ROOT = Path(__file__).parent.parent  # CTA folder
os.environ['PATH'] = str(PROJECT_ROOT) + os.pathsep + os.environ.get('PATH', '')
print(f"[Setup] Added to PATH: {PROJECT_ROOT}")

# Check if DLL exists
dll_path = PROJECT_ROOT / "PI_GCS2_DLL_x64.dll"
if dll_path.exists():
    print(f"[Setup] Found DLL: {dll_path}")
else:
    print(f"[Setup] WARNING: DLL not found at {dll_path}")

# Now import pipython
from pipython import GCSDevice

# List all connected USB devices
print("\nEnumerating USB devices...")
with GCSDevice() as pi:
    devices = pi.EnumerateUSB()
    print("Connected devices:")
    if devices:
        for dev in devices:
            print(f"  {dev}")
    else:
        print("  No devices found. Check USB connections and power.")
