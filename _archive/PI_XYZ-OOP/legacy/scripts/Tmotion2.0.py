#!/usr/bin/python
# -*- coding: "utf-8" -*-
"""
This example demonstrates how to control a 3-axis XYZ platform that uses
three independent controllers, one for each axis.
"""

from pipython import GCSDevice, pitools
import time
from origintools import reset, safe_range

# (c)2024 Physik Instrumente (PI) SE & Co. KG
# This code is provided for demonstration purposes only.
# Please review and adapt it to your specific hardware and application.

# --- Configuration Section ---
# Define the connection parameters for each individual controller.

CONTROLLER_CONFIG = {
    'X': {'port': 'COM5', 'baud': 115200, 'stage': '62309260', 'refmode': 'FPL', 'serialnum': '025550131'},
    'Y': {'port': 'COM3', 'baud': 115200, 'stage': '62309260', 'refmode': 'FPL', 'serialnum': '025550143'},
    'Z': {'port': 'COM4', 'baud': 115200, 'stage': '62309260', 'refmode': 'FPL', 'serialnum': '025550149'},
}

# Define a safe order for referencing the axes.
# For many XYZ systems, it's safest to reference Z first (to move it up and
# out of the way), then the other axes.
REFERENCE_ORDER = ['Z', 'X', 'Y']


# Define the real-world, intuitive travel range for each axis.
# Your safe_range function will use this to clamp values correctly.
# NOTE: I've assumed the Y-axis has a full 0-200 range. Please verify!
AXIS_TRAVEL_RANGES = {
    'X': {'min': 5.0, 'max': 200.0},
    'Y': {'min': 0.0, 'max': 200.0},
    'Z': {'min': 15.0, 'max': 200.0},
}



def main():
    pidevices = {}
    try:
        # -- Step 1: Connect to all controllers ---
        print("--- Connecting to all controllers ---")
        for axis, config in CONTROLLER_CONFIG.items():
            device = GCSDevice()
            device.ConnectUSB(serialnum=config['serialnum'])
            pidevices[axis] = device
            print(f"  {axis}-Axis Controller ({config['serialnum']}) connected: {pidevices[axis].qIDN().strip()}")

            # -- Step 2: Final, Robust Initialization Sequence ---
        print("\n--- Initializing and referencing all stages ---")
        for axis in REFERENCE_ORDER:
            pidevice = pidevices[axis]
            config = CONTROLLER_CONFIG[axis]
            ax = pidevice.axes[0]
            print(f"\nInitializing {axis}-axis stage...")
            print(f"  - Configuring stage '{config['stage']}' for axis {axis}...")
            pidevice.CST(ax, config['stage'])
            time.sleep(0.1)
            print(f"  - Enabling servo for axis {axis}...")
            pidevice.SVO(ax, True)
            print(f"  - Starting referencing move ('{config['refmode']}') for axis {axis}. This will cause motion.")
            ref_command = getattr(pidevice, config['refmode'])
            ref_command(ax)
            print(f"  - Waiting for {axis}-axis to complete referencing...")
            pitools.waitontarget(pidevice)
            print(f"  - Moving slightly off the limit switch...")
            pidevice.MVR(ax, -0.1)
            pitools.waitontarget(pidevice)
            print(f"  - {axis}-axis referenced and ready.")
            pos = pidevice.qPOS(ax)[ax]
            print(f"  - Position after referencing: {pos:.3f}")

            # -- NEW: Step 3: Set Motion Parameters ---
        print("\n--- Setting motion parameters ---")
        VELOCITY = 20.0  # Speed in mm/s (VT-80 max is 20 mm/s)
        for axis, pidevice in pidevices.items():
            ax = pidevice.axes[0]
            pidevice.VEL(ax, VELOCITY)
            print(f"  - Velocity for {axis}-axis set to {pidevice.qVEL(ax)[ax]:.2f} mm/s")

        # -- NEW: Step 4: User Confirmation Before Motion ---
        print("\n--- System Initialized and Ready for Motion ---")
        confirm = input("--> All stages are referenced. Proceed with motion sequence? [y/n]: ")
        if confirm.lower() != 'y':
            print("Motion cancelled by user. Exiting.")
            # We skip the rest of the 'try' block and go straight to 'finally' for cleanup.
            return


            # -- Step 3: Motion Sequence (This part remains correct) ---
        waypoints = [
            {'X': 10.0, 'Y': 5.0, 'Z': 20.0},
            {'X': 25.0, 'Y': 15.0, 'Z': 30.0},
            {'X': 50.0, 'Y': 20.0, 'Z': 15.0},
            {'X': 5.0, 'Y': 0.0, 'Z': 15.0}
        ]

        # ... (The rest of your motion and reset code is correct and does not need to be changed) ...

        print(f"\n--- Starting XYZ motion sequence for {len(waypoints)} waypoints ---")
        for i, target_pos in enumerate(waypoints):
            print(f"\nWaypoint {i + 1}: Commanding move to {target_pos}...")
            for axis, user_pos in target_pos.items():
                pidevice = pidevices[axis]
                target_axis = pidevice.axes[0]
                safe_pos = safe_range(axis, user_pos, AXIS_TRAVEL_RANGES)
                print(f"  - Commanding Axis {axis} to target {safe_pos:.3f}")
                pidevice.MOV(target_axis, safe_pos)

            print("  Waiting for all axes to reach target...")
            for axis in target_pos:
                pidevice = pidevices[axis]
                pitools.waitontarget(pidevice)
                print(f"  - Axis {axis} is on target.")

            print("\n  Move complete. Current positions:")
            for axis in ['X', 'Y', 'Z']:
                pidevice = pidevices[axis]
                pos = pidevice.qPOS(pidevice.axes[0])[pidevice.axes[0]]
                print(f"    Axis {axis}: {pos:.3f}")
            time.sleep(1)

        print('\nXYZ motion sequence finished.')

        # -- Step 6: Call the reset function (already includes a prompt) ---
        reset(pidevices, park_pos=200.0, prompt_user=True)

    except Exception as e:
        print(f"\nAn error occurred: {e}")

    finally:
        # -- Step 7: Cleanup --
        print("\n--- Closing all connections ---")
        for axis, device in pidevices.items():
            if device.IsConnected():
                print(f"  Closing connection to {axis}-axis controller...")
                device.CloseConnection()

if __name__ == '__main__':
    main()

