#!/usr/bin/python
# -*- coding: utf-8 -*-
"""
A universal visualizer for pipython scripts controlling 3-axis systems.
...
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
MOTION_PATH = []


# --- Simulator Class (Now with minimal printing) ---
class PIVisualizerSimulator:
    def __init__(self, *args, **kwargs):
        self.axis = 'Unknown';
        self.axes = ['1'];
        self._is_connected = False

    def ConnectUSB(self, serialnum):
        self._is_connected = True
        if serialnum in SERIAL_TO_AXIS_MAP: self.axis = SERIAL_TO_AXIS_MAP[serialnum]

    def qIDN(self):
        return f"Simulated Controller for Axis {self.axis}"

    def MOV(self, axis, target):
        if self.axis != 'Unknown': CURRENT_POSITION[self.axis] = target

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

    def SVO(self, *args, **kwargs):
        pass

    def CST(self, *args, **kwargs):
        pass

    def FPL(self, *args, **kwargs):
        pass

    def FNL(self, *args, **kwargs):
        pass


# --- Patcher Function (Now with minimal printing) ---
def patch_pipython_for_visualization():
    import pipython
    mock_pitools = MagicMock()

    def spy_startup(pidevice, stages=None, refmodes=None, **kwargs):
        CURRENT_POSITION[pidevice.axis] = 0.0

    def spy_waitontarget(pidevice, axes=None, **kwargs):
        if not MOTION_PATH:
            MOTION_PATH.append(CURRENT_POSITION.copy())
            return
        last_waypoint = MOTION_PATH[-1]
        if CURRENT_POSITION != last_waypoint:
            MOTION_PATH.append(CURRENT_POSITION.copy())

    mock_pitools.startup = spy_startup
    mock_pitools.waitontarget = spy_waitontarget
    pipython.GCSDevice = PIVisualizerSimulator
    pipython.pitools = mock_pitools


# --- REVISED Static Plot Function ---
def plot_motion_path(script_name):
    if not MOTION_PATH: print("\n--- No motion detected to plot. ---"); return
    print("\n--- Generating 3D Motion Plot ---")

    fig = plt.figure(figsize=(10, 8))
    ax = fig.add_subplot(111, projection='3d')
    TRAVEL_RANGE = (0, 200)
    ax.set(xlim=TRAVEL_RANGE, ylim=TRAVEL_RANGE, zlim=TRAVEL_RANGE,
           xlabel='X Axis (mm)', ylabel='Y Axis (mm)', zlabel='Z Axis (mm)',
           title=f'Motion Path from "{script_name}"')

    # Plot trajectory of the holder
    x_path = [p['X'] for p in MOTION_PATH]
    y_path = [p['Y'] for p in MOTION_PATH]
    z_path = [p['Z'] for p in MOTION_PATH]
    ax.plot(x_path, y_path, z_path, 'o-', color='purple', label='Holder Path')
    ax.scatter(x_path[0], y_path[0], z_path[0], color='green', s=100, label='Start')

    # Draw the final state of the gantry for context
    final_pos = MOTION_PATH[-1]
    x, y, z = final_pos['X'], final_pos['Y'], final_pos['Z']
    ax.plot([0, 200], [0, 0], [0, 0], color='gray', linestyle=':')  # X-Rail
    ax.plot([x, x], [0, 200], [0, 0], color='gray')  # Y-Rail
    ax.plot([x, x], [y, y], [0, 200], color='gray')  # Z-Rail
    ax.scatter(x, y, z, c='red', marker='X', s=150, label='End Position')

    ax.legend()
    ax.grid(True)
    plt.show()


# --- REVISED Gantry Animation Function ---
def animate_motion_path(script_name):
    if not MOTION_PATH: print("\n--- No motion detected to animate. ---"); return
    print("\n--- Generating 3D Gantry Animation ---")

    fig = plt.figure(figsize=(10, 8))
    ax = fig.add_subplot(111, projection='3d')
    TRAVEL_RANGE = (0, 200)
    ax.set(xlim=TRAVEL_RANGE, ylim=TRAVEL_RANGE, zlim=TRAVEL_RANGE,
           xlabel='X Axis (mm)', ylabel='Y Axis (mm)', zlabel='Z Axis (mm)',
           title=f'Gantry Animation for "{script_name}"')

    # Static element: The base X-Rail
    ax.plot([0, 200], [0, 0], [0, 0], color='black', linestyle='-', linewidth=3, label='X-Rail (Base)')

    # Dynamic elements that will be updated in each frame
    (y_rail,) = ax.plot([], [], [], color='blue', linewidth=3, label='Y-Rail')
    (z_rail,) = ax.plot([], [], [], color='green', linewidth=3, label='Z-Rail')
    (holder,) = ax.plot([], [], [], 'X', markersize=12, color='red', label='Holder')
    (path_history,) = ax.plot([], [], [], ':', color='purple', label='Path History')
    ax.legend()

    def update(frame):
        pos = MOTION_PATH[frame]
        x, y, z = pos['X'], pos['Y'], pos['Z']

        # The Y-Rail is mounted on the X-carriage, so its position is defined by x.
        y_rail.set_data_3d([x, x], [0, 200], [0, 0])

        # The Z-Rail is mounted on the Y-carriage, defined by x and y.
        z_rail.set_data_3d([x, x], [y, y], [0, 200])

        # The holder (end-effector) moves along the Z-rail.
        holder.set_data_3d([x], [y], [z])

        # Trace the path of the holder
        hist_x = [p['X'] for p in MOTION_PATH[:frame + 1]]
        hist_y = [p['Y'] for p in MOTION_PATH[:frame + 1]]
        hist_z = [p['Z'] for p in MOTION_PATH[:frame + 1]]
        path_history.set_data_3d(hist_x, hist_y, hist_z)

        return y_rail, z_rail, holder, path_history

    ani = animation.FuncAnimation(fig, update, frames=len(MOTION_PATH), blit=True, interval=500)
    plt.show()


# --- Main Function (Handles script loading and execution) ---
def main():
    if len(sys.argv) < 2:
        print("Usage: python pi_visualizer.py <your_script.py> [--animate]")
        sys.exit(1)
    motion_script_path = sys.argv[1]
    do_animation = '--animate' in sys.argv
    try:
        spec = importlib.util.spec_from_file_location("ts", motion_script_path)
        target_script = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(target_script)
        if hasattr(target_script, 'CONTROLLER_CONFIG'):
            config = target_script.CONTROLLER_CONFIG
            for axis, params in config.items():
                SERIAL_TO_AXIS_MAP[params['serialnum']] = axis
        else:
            print("ERROR: 'CONTROLLER_CONFIG' not in target script.");
            sys.exit(1)
    except Exception as e:
        print(f"ERROR: Failed to load target script: {e}");
        sys.exit(1)

    patch_pipython_for_visualization()
    print("--- PIPython has been replaced by the visualizer ---")
    print(f"--- Simulating motion from: {motion_script_path} ---\n")

    try:
        runpy.run_path(motion_script_path, run_name='__main__')
        print("\n--- Simulation Complete ---")
    except Exception as e:
        print(f"\n--- Error during script execution: {e} ---")

    if do_animation:
        animate_motion_path(motion_script_path)
    else:
        plot_motion_path(motion_script_path)


if __name__ == '__main__':
    main()