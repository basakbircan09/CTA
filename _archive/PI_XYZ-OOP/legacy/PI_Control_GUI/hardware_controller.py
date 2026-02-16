#!/usr/bin/python
# -*- coding: utf-8 -*-
"""
Hardware Controller Module
Manages actual PI stage hardware connections and operations
Based on Tmotion2.0.py hardware control logic
"""

import sys
import os
import time
from pipython import GCSDevice, pitools

# Add parent directory to path to import origintools
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from origintools import safe_range

from config import (CONTROLLER_CONFIG, REFERENCE_ORDER, AXIS_TRAVEL_RANGES,
                   MAX_VELOCITY, DEFAULT_PARK_POSITION)


class PIHardwareController:
    """
    Hardware controller for PI 3-axis stage system.
    Handles connection, initialization, motion, and cleanup.
    """

    def __init__(self):
        self.pidevices = {}
        self.connected = False
        self.initialized = False
        self.current_positions = {'X': 0.0, 'Y': 0.0, 'Z': 0.0}
        self.velocities = {'X': 10.0, 'Y': 10.0, 'Z': 10.0}

    def connect_controllers(self):
        """
        Connect to all three axis controllers via USB.
        Returns: (success: bool, message: str)
        """
        try:
            print("--- Connecting to all controllers ---")
            for axis, config in CONTROLLER_CONFIG.items():
                device = GCSDevice()
                device.ConnectUSB(serialnum=config['serialnum'])
                self.pidevices[axis] = device
                idn = self.pidevices[axis].qIDN().strip()
                print(f"  {axis}-Axis Controller ({config['serialnum']}) connected: {idn}")

            self.connected = True
            return True, "All controllers connected successfully"

        except Exception as e:
            error_msg = f"Connection failed: {str(e)}"
            print(error_msg)
            # Cleanup any partial connections
            self.disconnect_controllers()
            return False, error_msg

    def initialize_and_reference(self):
        """
        Initialize and reference all stages in safe order (Z, X, Y).
        This performs the full initialization sequence from Tmotion2.0.py.
        Returns: (success: bool, message: str)
        """
        if not self.connected:
            return False, "Controllers not connected. Please connect first."

        try:
            print("\n--- Initializing and referencing all stages ---")

            for axis in REFERENCE_ORDER:
                pidevice = self.pidevices[axis]
                config = CONTROLLER_CONFIG[axis]
                ax = pidevice.axes[0]

                print(f"\nInitializing {axis}-axis stage...")

                # Configure stage
                print(f"  - Configuring stage '{config['stage']}' for axis {axis}...")
                pidevice.CST(ax, config['stage'])
                time.sleep(0.1)

                # Enable servo
                print(f"  - Enabling servo for axis {axis}...")
                pidevice.SVO(ax, True)

                # Start referencing
                print(f"  - Starting referencing move ('{config['refmode']}') for axis {axis}. This will cause motion.")
                ref_command = getattr(pidevice, config['refmode'])
                ref_command(ax)

                # Wait for referencing to complete
                print(f"  - Waiting for {axis}-axis to complete referencing...")
                pitools.waitontarget(pidevice)

                # Move slightly off limit switch
                print(f"  - Moving slightly off the limit switch...")
                pidevice.MVR(ax, -0.1)
                pitools.waitontarget(pidevice)

                print(f"  - {axis}-axis referenced and ready.")
                pos = pidevice.qPOS(ax)[ax]
                self.current_positions[axis] = pos
                print(f"  - Position after referencing: {pos:.3f}")

            # Set motion parameters
            print("\n--- Setting motion parameters ---")
            for axis, pidevice in self.pidevices.items():
                ax = pidevice.axes[0]
                pidevice.VEL(ax, self.velocities[axis])
                actual_vel = pidevice.qVEL(ax)[ax]
                print(f"  - Velocity for {axis}-axis set to {actual_vel:.2f} mm/s")

            self.initialized = True
            return True, "All stages initialized and referenced successfully"

        except Exception as e:
            error_msg = f"Initialization failed: {str(e)}"
            print(error_msg)
            return False, error_msg

    def set_velocity(self, axis, velocity):
        """
        Set velocity for specified axis.
        Args:
            axis: 'X', 'Y', or 'Z'
            velocity: velocity in mm/s (will be clamped to MAX_VELOCITY)
        Returns: (success: bool, message: str)
        """
        if not self.initialized:
            return False, "System not initialized"

        try:
            if velocity <= 0:
                return False, "Velocity must be positive"

            if velocity > MAX_VELOCITY:
                velocity = MAX_VELOCITY
                msg = f"Velocity clamped to maximum {MAX_VELOCITY} mm/s"
                print(msg)

            pidevice = self.pidevices[axis]
            ax = pidevice.axes[0]
            pidevice.VEL(ax, velocity)
            self.velocities[axis] = velocity

            return True, f"Velocity set to {velocity:.2f} mm/s"

        except Exception as e:
            return False, f"Failed to set velocity: {str(e)}"

    def move_absolute(self, axis, target_position):
        """
        Move axis to absolute position (MOV command).
        Position will be clamped to safe range.
        Args:
            axis: 'X', 'Y', or 'Z'
            target_position: target position in mm
        Returns: (success: bool, message: str)
        """
        if not self.initialized:
            return False, "System not initialized"

        try:
            # Apply safe range clamping
            safe_pos = safe_range(axis, target_position, AXIS_TRAVEL_RANGES)

            pidevice = self.pidevices[axis]
            ax = pidevice.axes[0]
            pidevice.MOV(ax, safe_pos)

            return True, f"Moving {axis} to {safe_pos:.3f} mm"

        except Exception as e:
            return False, f"Move failed: {str(e)}"

    def move_relative(self, axis, distance):
        """
        Move axis by relative distance (MVR command).
        Final position will be clamped to safe range.
        Args:
            axis: 'X', 'Y', or 'Z'
            distance: relative distance in mm (positive or negative)
        Returns: (success: bool, message: str)
        """
        if not self.initialized:
            return False, "System not initialized"

        try:
            # Calculate target position and apply safe range
            current_pos = self.get_position(axis)
            target_pos = current_pos + distance
            safe_pos = safe_range(axis, target_pos, AXIS_TRAVEL_RANGES)

            # Calculate actual distance to move
            actual_distance = safe_pos - current_pos

            pidevice = self.pidevices[axis]
            ax = pidevice.axes[0]
            pidevice.MVR(ax, actual_distance)

            return True, f"Moving {axis} by {actual_distance:.3f} mm"

        except Exception as e:
            return False, f"Relative move failed: {str(e)}"

    def wait_for_target(self, axis=None):
        """
        Wait for axis/axes to reach target position.
        Args:
            axis: specific axis to wait for, or None for all axes
        """
        if not self.initialized:
            return

        try:
            if axis:
                pitools.waitontarget(self.pidevices[axis])
            else:
                for ax in ['X', 'Y', 'Z']:
                    pitools.waitontarget(self.pidevices[ax])
        except Exception as e:
            print(f"Error waiting for target: {str(e)}")

    def get_position(self, axis):
        """
        Get current position of axis (qPOS command).
        Args:
            axis: 'X', 'Y', or 'Z'
        Returns: position in mm, or 0.0 if error
        """
        if not self.initialized:
            return 0.0

        try:
            pidevice = self.pidevices[axis]
            ax = pidevice.axes[0]
            pos = pidevice.qPOS(ax)[ax]
            self.current_positions[axis] = pos
            return pos
        except Exception as e:
            print(f"Error reading position for {axis}: {str(e)}")
            return self.current_positions[axis]

    def get_all_positions(self):
        """
        Get current positions of all axes.
        Returns: dict {'X': pos_x, 'Y': pos_y, 'Z': pos_z}
        """
        return {
            'X': self.get_position('X'),
            'Y': self.get_position('Y'),
            'Z': self.get_position('Z')
        }

    def is_on_target(self, axis):
        """
        Check if axis is on target.
        Args:
            axis: 'X', 'Y', or 'Z'
        Returns: bool
        """
        if not self.initialized:
            return False

        try:
            pidevice = self.pidevices[axis]
            ax = pidevice.axes[0]
            return pidevice.qONT(ax)[ax]
        except Exception as e:
            print(f"Error checking on-target for {axis}: {str(e)}")
            return False

    def stop_all(self):
        """
        Emergency stop - halt all motion immediately.
        """
        if not self.connected:
            return

        try:
            for axis, pidevice in self.pidevices.items():
                pidevice.STP()
                print(f"Stopped {axis}-axis")
        except Exception as e:
            print(f"Error during stop: {str(e)}")

    def reset_to_park(self, park_position=DEFAULT_PARK_POSITION):
        """
        Reset all axes to park position using safe sequence from origintools.
        Z moves first, then X and Y simultaneously.
        Args:
            park_position: target park position in mm
        Returns: (success: bool, message: str)
        """
        if not self.initialized:
            return False, "System not initialized"

        try:
            print(f"\n--- Starting Reset Sequence: Moving all axes to {park_position} ---")

            # Step 1: Park Z-Axis First (Safety)
            if 'Z' in self.pidevices:
                print("  - Moving Z-axis to park position...")
                self.pidevices['Z'].MOV(self.pidevices['Z'].axes[0], park_position)
                pitools.waitontarget(self.pidevices['Z'])
                print("  - Axis Z is parked.")

            # Step 2: Park X and Y Axes Simultaneously (Efficiency)
            xy_axes_to_move = [axis for axis in ['X', 'Y'] if axis in self.pidevices]

            if xy_axes_to_move:
                print("  - Commanding X and Y axes to park position...")
                for axis in xy_axes_to_move:
                    self.pidevices[axis].MOV(self.pidevices[axis].axes[0], park_position)

                print("  - Waiting for X and Y to park...")
                for axis in xy_axes_to_move:
                    pitools.waitontarget(self.pidevices[axis])
                    print(f"  - Axis {axis} is parked.")

            print("\n--- Reset Sequence Finished ---")
            return True, "All axes parked successfully"

        except Exception as e:
            error_msg = f"Reset failed: {str(e)}"
            print(error_msg)
            return False, error_msg

    def disconnect_controllers(self):
        """
        Close all controller connections.
        """
        print("\n--- Closing all connections ---")
        for axis, device in self.pidevices.items():
            try:
                if device.IsConnected():
                    print(f"  Closing connection to {axis}-axis controller...")
                    device.CloseConnection()
            except Exception as e:
                print(f"  Error closing {axis}-axis: {str(e)}")

        self.pidevices.clear()
        self.connected = False
        self.initialized = False
        print("All connections closed.")

    def __del__(self):
        """Cleanup on object destruction."""
        self.disconnect_controllers()
