#!/usr/bin/python
# -*- coding: utf-8 -*-
"""
This is a utility module for custom, reusable PI controller functions.
"""

from pipython import pitools

# Central dictionary for custom safe travel ranges.
AXIS_SAFE_RANGES = {
    'X': (5.0, 200.0),
    'Y': (0.0, 200.0),
    'Z': (15.0, 200.0),
}

# --- Your updated safe_range function (in origintools.py) ---

# Make sure to pass the AXIS_TRAVEL_RANGES dictionary to it from your main script,
# or import it directly.

def safe_range(axis, target_pos, travel_ranges):
    """
    Clamps the target_pos to the defined physical limits for the given axis.
    """
    min_limit = travel_ranges[axis]['min']
    max_limit = travel_ranges[axis]['max']

    if target_pos < min_limit:
        print(f"INFO: Target {target_pos} for axis {axis} is out of bounds ({min_limit}, {max_limit}). Clamping to {min_limit}.")
        return min_limit
    if target_pos > max_limit:
        print(f"INFO: Target {target_pos} for axis {axis} is out of bounds ({min_limit}, {max_limit}). Clamping to {max_limit}.")
        return max_limit
    return target_pos





"""reset_2.0 for parking all axes backto PL in 2 times"""

def reset(pidevices, park_pos=200.0, prompt_user=False):
    """
    Moves all axes to a defined parking position safely. Z is moved first,
    then X and Y are moved simultaneously for efficiency.

    Args:
        pidevices (dict): Dictionary of connected GCSDevice objects.
        park_pos (float): The target coordinate for all axes.
        prompt_user (bool): If True, waits for user 'y/n' confirmation before starting.
    """
    if prompt_user:
        try:
            choice = input("\nMotion sequence finished. Reset all stages to park position? [y/n]: ").lower().strip()
            if choice != 'y':
                print("Reset cancelled by user. Stages will remain at their current positions.")
                return
        except (EOFError, KeyboardInterrupt):
            print("\nReset cancelled. Exiting.")
            return

    print(f"\n--- Starting Reset Sequence: Moving all axes to {park_pos} ---")

    # --- Step 1: Park Z-Axis First (Safety) ---
    if 'Z' in pidevices:
        try:
            print("  - Moving Z-axis to park position...")
            pidevices['Z'].MOV(pidevices['Z'].axes[0], park_pos)
            pitools.waitontarget(pidevices['Z'])
            print("  - Axis Z is parked.")
        except Exception as e:
            print(f"  ERROR: Could not move Z-axis. {e}")
            # If Z fails to park, we should not proceed with other moves.
            return

            # --- Step 2: Park X and Y Axes Simultaneously (Efficiency) ---
    xy_axes_to_move = [axis for axis in ['X', 'Y'] if axis in pidevices]

    if xy_axes_to_move:
        # -- COMMAND X AND Y TO MOVE --
        print("  - Commanding X and Y axes to park position...")
        for axis in xy_axes_to_move:
            try:
                pidevices[axis].MOV(pidevices[axis].axes[0], park_pos)
            except Exception as e:
                print(f"  ERROR: Could not send move command to {axis}-axis. {e}")

        # -- WAIT FOR X AND Y TO COMPLETE --
        print("  - Waiting for X and Y to park...")
        for axis in xy_axes_to_move:
            try:
                pitools.waitontarget(pidevices[axis])
                print(f"  - Axis {axis} is parked.")
            except Exception as e:
                print(f"  ERROR: While waiting for {axis}-axis. {e}")

    print("\n--- Reset Sequence Finished ---")