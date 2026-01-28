#!/usr/bin/python
# -*- coding: "utf-8" -*-
"""
This example demonstrates how to control a 3-axis XYZ platform that uses
three independent controllers, one for each axis.
"""

from pipython import GCSDevice, pitools
import time

# (c)2024 Physik Instrumente (PI) SE & Co. KG
# This code is provided for demonstration purposes only.
# Please review and adapt it to your specific hardware and application.

# --- Configuration Section ---
# Define the connection parameters for each individual controller.

CONTROLLER_CONFIG = {
    'X': {'port': 'COM5', 'baud': 115200, 'stage': '62309220', 'refmode': 'FPL', 'serialnum': '025550131'},
    'Y': {'port': 'COM3', 'baud': 115200, 'stage': '62309220', 'refmode': 'FPL', 'serialnum': '025550143'},
    'Z': {'port': 'COM4', 'baud': 115200, 'stage': '62309220', 'refmode': 'FPL', 'serialnum': '025550149'},
}

# Define a safe order for referencing the axes.
# For many XYZ systems, it's safest to reference Z first (to move it up and
# out of the way), followed by X and Y. PLEASE VERIFY FOR CURRENT SYSTEM.
SAFE_REF_ORDER = ['Z', 'X', 'Y']


def main():
    """Connects, initializes, and moves a 3-controller XYZ system."""
    pidevices = {}  # Dictionary to hold our connected GCSDevice objects.

    try:
        # -- Step 1: Connect to all controllers --
        print("--- Connecting to all controllers ---")
        for axis in SAFE_REF_ORDER:
            config = CONTROLLER_CONFIG[axis]
            print(f"Connecting to Axis {axis} on {config['port']}...")

            # Create a separate GCSDevice instance for each controller.
            pidevice = GCSDevice()
            # PISerial.py defines the ConnectRS232 method for COM port connections.
            pidevice.ConnectUSB(serialnum=config['serialnum'])
            print(f"  Connected: {pidevice.qIDN().strip()}")
            pidevices[axis] = pidevice

        # -- Step 2: Initialize all stages in a safe order --
        print("\n--- Initializing all stages (referencing) ---")
        for axis in SAFE_REF_ORDER:
            config = CONTROLLER_CONFIG[axis]
            pidevice = pidevices[axis]
            print(f"Initializing Axis {axis}...")
            # pitools.startup is called on each individual device object.
            pitools.startup(pidevice, stages=[config['stage']], refmodes=[config['refmode']])
            print(f"  Axis {axis} is referenced.")

        # -- Step 3: Coordinated Movement --
        waypoints = [
            {'X': 10.0, 'Y': 5.0, 'Z': 2.0},
            {'X': 25.0, 'Y': 15.0, 'Z': 8.0},
            {'X': 0.0, 'Y': 0.0, 'Z': 0.0},
        ]

        print("\n--- Starting coordinated motion sequence ---")
        confirm = input("--> Ready to start motion? [y/n]: ")
        if confirm.lower() != 'y':
            print("Motion cancelled by user.")
            return

        for i, target in enumerate(waypoints):
            print(f"\nWaypoint {i + 1}: Moving to {target}...")

            # --- The "Simultaneous" Move Technique ---
            # 1. Send the MOV command to EACH controller without waiting.
            #    The commands are sent nearly instantly, starting the moves together.
            for axis, pos in target.items():
                pidevices[axis].MOV(pidevices[axis].axes[0], pos)

            # 2. THEN, wait for EACH controller to report its move is complete.
            print("  Waiting for all axes to reach target...")
            for axis in target:
                pitools.waitontarget(pidevices[axis])

            print("  Move complete. Current positions:")
            for axis in ['X', 'Y', 'Z']:
                pos = pidevices[axis].qPOS()[pidevices[axis].axes[0]]
                print(f"    Axis {axis}: {pos:.3f}")

            time.sleep(1)

        print('\nXYZ motion sequence finished.')

    finally:
        # -- Step 4: Cleanup --
        # This "finally" block ensures that no matter what happens,
        # we attempt to close every connection that was successfully opened.
        print("\n--- Closing all connections ---")
        for axis, pidevice in pidevices.items():
            if pidevice.IsConnected():
                print(f"Closing connection for Axis {axis}.")
                pidevice.CloseConnection()


if __name__ == '__main__':
    main()