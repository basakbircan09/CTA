#!/usr/bin/python
# -*- coding: utf-8 -*-
"""
A universal visualizer for pipython scripts controlling 3-axis systems.
... (rest of docstring) ...

Now includes a realistic 3D gantry animation feature.
Usage:
    python pi_visualizer.py <your_script.py> [--animate]
"""

import sys
import runpy
import importlib.util
from unittest.mock import MagicMock
import matplotlib.pyplot as plt
from mpl_toolkits.mplot3d import Axes3D
import matplotlib.animation as animation

# --- Global State and Data Recording ---
SERIAL_TO_AXIS_MAP = {}
CURRENT_POSITION = {'X': 0.0, 'Y': 0.0, 'Z': 0.0}
MOTION_PATH = []  # Start with an empty path


# --- Simulator Class (PIVisualizerSimulator) remains the same ---
class PIVisualizerSimulator:
    # ... (no changes to this class) ...
    def __init__(self, *args, **kwargs):
        self.axis = 'Unknown';
        self.axes = ['1'];
        self._is_connected = False

    def ConnectUSB(self, serialnum):
        self._is_connected = True
        if serialnum in SERIAL_TO_AXIS_MAP: self.axis = SERIAL_TO_AXIS_MAP[serialnum]
        print(f"SIM: ConnectUSB for serial '{serialnum}' -> Axis {self.axis}")

    def qIDN(self):
        return f"Simulated Controller for Axis {self.axis}"

    def MOV(self, axis, target):
        if self.axis != 'Unknown':
            print(f"SIM: MOV command for Axis {self.axis} to {target:.3f}")
            CURRENT_POSITION[self.axis] = target

    def IsConnected(self):
        return self._is_connected

    def CloseConnection(self):
        self._is_connected = False

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        pass

    def qPOS(self, axis=None):
        return {self.axes[0]: CURRENT_POSITION.get(self.axis, 0.0)}


# --- Patcher Function (with corrected waitontarget logic) ---
def patch_pipython_for_visualization():
    import pipython
    mock_pitools = MagicMock()

    def spy_startup(pidevice, stages=None, refmodes=None, **kwargs):
        print(f"SIM: pitools.startup called for Axis {pidevice.axis}")

    def spy_waitontarget(pidevice, axes=None, **kwargs):
        if not MOTION_PATH:
            print(f"SIM: First reference complete. Recording START waypoint: {CURRENT_POSITION}")
            MOTION_PATH.append(CURRENT_POSITION.copy())
            return
        last_waypoint = MOTION_PATH[-1]
        if CURRENT_POSITION != last_waypoint:
            print(f"SIM: waitontarget triggered. Recording new waypoint: {CURRENT_POSITION}")
            MOTION_PATH.append(CURRENT_POSITION.copy())

    mock_pitools.startup = spy_startup
    mock_pitools.waitontarget = spy_waitontarget
    pipython.GCSDevice = PIVisualizerSimulator
    pipython.pitools = mock_pitools
    print("--- PIPython has been replaced with the motion visualization simulator ---")


# --- Static Plotting Function (Unchanged) ---
def plot_motion_path(script_name):
    # ... (no changes to this function, it now works correctly) ...
    if not MOTION_PATH: print("\n--- No motion detected to plot. ---"); return
    print("\n--- Generating 3D Motion Plot ---")
    x = [p['X'] for p in MOTION_PATH];
    y = [p['Y'] for p in MOTION_PATH];
    z = [p['Z'] for p in MOTION_PATH]
    fig = plt.figure(figsize=(8, 6));
    ax = fig.add_subplot(111, projection='3d')
    ax.plot(x, y, z, 'o-', label='Tool-tip Trajectory')
    ax.scatter(x[0], y[0], z[0], color='green', s=100, label='Start', depthshade=False)
    ax.scatter(x[-1], y[-1], z[-1], color='red', s=100, label='End', depthshade=False)
    ax.set_xlabel('X Axis (mm)');
    ax.set_ylabel('Y Axis (mm)');
    ax.set_zlabel('Z Axis (mm)')
    ax.set_title(f'Visualized Motion Path from "{script_name}"');
    ax.legend();
    ax.grid(True)
    plt.show()


# --- NEW Gantry Animation Function ---
def animate_motion_path(script_name):
    """Generates and displays a 3D animation of the gantry system."""
    if not MOTION_PATH: print("\n--- No motion detected to animate. ---"); return
    print("\n--- Generating 3D Gantry Animation ---")

    fig = plt.figure(figsize=(10, 8))
    ax = fig.add_subplot(111, projection='3d')

    # Define the travel range for the visualization rails.
    # We can set this based on the VT-80's capabilities.
    TRAVEL_RANGE = (0, 50)
    ax.set_xlim(TRAVEL_RANGE);
    ax.set_ylim(TRAVEL_RANGE);
    ax.set_zlim(TRAVEL_RANGE)
    ax.set_xlabel('X Axis');
    ax.set_ylabel('Y Axis');
    ax.set_zlabel('Z Axis')
    ax.set_title(f'Gantry Animation for "{script_name}"')

    # Draw static rails for reference
    ax.plot([TRAVEL_RANGE[0], TRAVEL_RANGE[1]], [0, 0], [0, 0], color='gray', linestyle='--')
    ax.plot([0, 0], [TRAVEL_RANGE[0], TRAVEL_RANGE[1]], [0, 0], color='gray', linestyle='--')

    # These are the plot objects that will be updated in each frame
    (x_carriage,) = ax.plot([], [], [], 's', markersize=10, color='blue', label='X-Y Stage')
    (z_carriage,) = ax.plot([], [], [], 'o', markersize=10, color='green', label='Z Stage')
    (z_arm,) = ax.plot([], [], [], '-', linewidth=3, color='green')
    (tool_tip,) = ax.plot([], [], [], 'X', markersize=12, color='red', label='Tool Tip (Holder)')
    (trajectory_line,) = ax.plot([], [], [], ':', color='purple', label='Path History')

    ax.legend(loc='upper right')

    # Animation update function
    def update(frame):
        pos = MOTION_PATH[frame]
        x, y, z = pos['X'], pos['Y'], pos['Z']

        # The X carriage moves along X, and carries the Y rail
        x_carriage.set_data_3d([x], [y], [TRAVEL_RANGE[1]])

        # The Z arm moves with the X-Y stage
        z_arm.set_data_3d([x, x], [y, y], [TRAVEL_RANGE[1], z])
        z_carriage.set_data_3d([x], [y], [z])
        tool_tip.set_data_3d([x], [y], [z])

        # Update the history of the trajectory
        hist_x = [p['X'] for p in MOTION_PATH[:frame + 1]]
        hist_y = [p['Y'] for p in MOTION_PATH[:frame + 1]]
        hist_z = [p['Z'] for p in MOTION_PATH[:frame + 1]]
        trajectory_line.set_data_3d(hist_x, hist_y, hist_z)

        return x_carriage, z_carriage, z_arm, tool_tip, trajectory_line

    # Create and run the animation
    ani = animation.FuncAnimation(fig, update, frames=len(MOTION_PATH), blit=True, interval=500)
    plt.show()


# --- Main Function (Updated to handle --animate flag) ---
def main():
    if len(sys.argv) < 2:
        print("Usage: python pi_visualizer.py <your_script.py> [--animate]")
        sys.exit(1)

    motion_script_path = sys.argv[1]
    do_animation = '--animate' in sys.argv

    # ... (Step 1: Safely load script and build SERIAL_TO_AXIS_MAP - no changes) ...
    try:
        spec = importlib.util.spec_from_file_location("ts", motion_script_path)
        target_script = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(target_script)
        if hasattr(target_script, 'CONTROLLER_CONFIG'):
            config = target_script.CONTROLLER_CONFIG
            for axis, params in config.items():
                SERIAL_TO_AXIS_MAP[params['serialnum']] = axis
            print(f"--- Simulator map configured: {SERIAL_TO_AXIS_MAP} ---")
        else:
            print("ERROR: 'CONTROLLER_CONFIG' not in target script.");
            sys.exit(1)
    except Exception as e:
        print(f"ERROR: Failed to load target script: {e}");
        sys.exit(1)

    # --- Step 2: Patch pipython ---
    patch_pipython_for_visualization()

    # --- Step 3: Run the script's logic ---
    print(f"\n--- Simulating script: {motion_script_path} ---\n")
    try:
        runpy.run_path(motion_script_path, run_name='__main__')
    except Exception as e:
        print(f"\n--- Error during script execution: {e} ---")

    # --- Step 4: Plot or Animate based on the flag ---
    if do_animation:
        animate_motion_path(motion_script_path)
    else:
        plot_motion_path(motion_script_path)


if __name__ == '__main__':
    main()