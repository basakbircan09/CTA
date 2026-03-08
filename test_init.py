import os
from pathlib import Path

# Setup DLL path
PROJECT_ROOT = Path(__file__).parent.parent if '__file__' in dir() else Path.cwd()
os.environ['PATH'] = str(PROJECT_ROOT) + os.pathsep + os.environ.get('PATH', '')

from pipython import GCSDevice, pitools
import time

SERIAL = '025550149'  # Z-axis (test with one first)
STAGE = '62309260'

print(f"Connecting to controller {SERIAL}...")
with GCSDevice() as pi:
    pi.ConnectUSB(serialnum=SERIAL)
    print(f"Connected: {pi.qIDN().strip()}")

    ax = pi.axes[0]
    print(f"Axis: {ax}")

    # Check available stages
    print("\nAvailable stages:")
    try:
        stages = pi.qVST()
        print(stages)
    except:
        print("  Could not query stages")

    # Try to configure stage
    print(f"\nConfiguring stage '{STAGE}'...")
    try:
        pi.CST(ax, STAGE)
        print("  Stage configured successfully")
    except Exception as e:
        print(f"  ERROR: {e}")

    # Check current stage
    print(f"\nCurrent stage config:")
    try:
        current = pi.qCST()
        print(f"  {current}")
    except Exception as e:
        print(f"  Could not query: {e}")

    # Try to enable servo
    print(f"\nEnabling servo...")
    try:
        pi.SVO(ax, True)
        print("  Servo enabled")
    except Exception as e:
        print(f"  ERROR: {e}")

print("\nDone!")
