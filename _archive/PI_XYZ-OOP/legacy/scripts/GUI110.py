#!/usr/bin/python
# -*- coding: utf-8 -*-
"""
PI Stage Control GUI using tkinter
Run this file directly in PyCharm to launch the GUI
"""

import tkinter as tk
from tkinter import ttk, messagebox
import threading
import time


class PIStageGUI:
    def __init__(self, root):
        self.root = root
        self.root.title("PI Stage Control System")
        self.root.geometry("1000x800")
        self.root.configure(bg='#2d3748')

        # Current position state (simulates qPOS() response)
        self.current_pos = {'X': 0.0, 'Y': 0.0, 'Z': 0.0}

        # Velocity settings
        self.velocity = {'X': 10.0, 'Y': 10.0, 'Z': 10.0}

        # Safe ranges from Tmotion2.0.py AXIS_TRAVEL_RANGES
        self.SAFE_RANGES = {
            'X': {'min': 5.0, 'max': 200.0},
            'Y': {'min': 0.0, 'max': 200.0},
            'Z': {'min': 15.0, 'max': 200.0}
        }

        self.MAX_VELOCITY = 20.0  # VT-80 max velocity from Tmotion script

        # Mode and automation state
        self.mode = tk.StringVar(value='manual')
        self.is_running = False
        self.waypoints = [
            {'X': 10.0, 'Y': 5.0, 'Z': 20.0, 'holdTime': 1.0},
            {'X': 25.0, 'Y': 15.0, 'Z': 30.0, 'holdTime': 2.0}
        ]
        self.step_size = 1.0
        self.connected = False

        self.setup_gui()
        self.update_position_display()

    def setup_gui(self):
        # Main container
        main_frame = tk.Frame(self.root, bg='#2d3748')
        main_frame.pack(fill='both', expand=True, padx=10, pady=10)

        # Title
        title_label = tk.Label(main_frame, text="PI Stage Control System",
                               font=('Arial', 20, 'bold'), bg='#2d3748', fg='white')
        title_label.pack(pady=(0, 20))

        # Connection frame
        self.setup_connection_frame(main_frame)

        # Position display frame
        self.setup_position_frame(main_frame)

        # Mode selection frame
        self.setup_mode_frame(main_frame)

        # Velocity settings frame
        self.setup_velocity_frame(main_frame)

        # Control frames (manual/automated)
        self.manual_frame = tk.Frame(main_frame, bg='#2d3748')
        self.automated_frame = tk.Frame(main_frame, bg='#2d3748')

        self.setup_manual_control()
        self.setup_automated_control()

        # Initially show manual control
        self.show_manual_control()

    def setup_connection_frame(self, parent):
        """Connection status and controls"""
        conn_frame = tk.LabelFrame(parent, text="Connection", bg='#4a5568', fg='white')
        conn_frame.pack(fill='x', pady=(0, 10))

        self.conn_status = tk.Label(conn_frame, text="Disconnected",
                                    fg='red', bg='#4a5568')
        self.conn_status.pack(side='left', padx=10)

        tk.Button(conn_frame, text="Connect", command=self.connect_devices,
                  bg='#3182ce', fg='white').pack(side='right', padx=10, pady=5)

    def setup_position_frame(self, parent):
        """Current position display - simulates qPOS() readout"""
        pos_frame = tk.LabelFrame(parent, text="Current Position", bg='#4a5568', fg='white')
        pos_frame.pack(fill='x', pady=(0, 10))

        self.pos_labels = {}
        position_container = tk.Frame(pos_frame, bg='#4a5568')
        position_container.pack(fill='x', padx=10, pady=10)

        for i, axis in enumerate(['X', 'Y', 'Z']):
            axis_frame = tk.Frame(position_container, bg='#4a5568')
            axis_frame.grid(row=0, column=i, padx=20, pady=10, sticky='ew')

            tk.Label(axis_frame, text=f"{axis}-Axis", font=('Arial', 14, 'bold'),
                     bg='#4a5568', fg='white').pack()

            self.pos_labels[axis] = tk.Label(axis_frame, text="0.000",
                                             font=('Arial', 16, 'bold'),
                                             fg='cyan', bg='#4a5568')
            self.pos_labels[axis].pack()

            tk.Label(axis_frame, text="mm", bg='#4a5568', fg='white').pack()

            range_text = f"[{self.SAFE_RANGES[axis]['min']}-{self.SAFE_RANGES[axis]['max']}]"
            tk.Label(axis_frame, text=range_text, font=('Arial', 8),
                     fg='gray', bg='#4a5568').pack()

        position_container.grid_columnconfigure(0, weight=1)
        position_container.grid_columnconfigure(1, weight=1)
        position_container.grid_columnconfigure(2, weight=1)

    def setup_mode_frame(self, parent):
        """Mode selection"""
        mode_frame = tk.LabelFrame(parent, text="Control Mode", bg='#4a5568', fg='white')
        mode_frame.pack(fill='x', pady=(0, 10))

        tk.Radiobutton(mode_frame, text="Manual Mode", variable=self.mode, value='manual',
                       command=self.mode_changed, bg='#4a5568', fg='white',
                       selectcolor='#3182ce').pack(side='left', padx=10, pady=5)

        tk.Radiobutton(mode_frame, text="Automated Mode", variable=self.mode, value='automated',
                       command=self.mode_changed, bg='#4a5568', fg='white',
                       selectcolor='#3182ce').pack(side='left', padx=10, pady=5)

    def setup_velocity_frame(self, parent):
        """Velocity settings - simulates VEL() commands"""
        vel_frame = tk.LabelFrame(parent, text="Velocity Settings", bg='#4a5568', fg='white')
        vel_frame.pack(fill='x', pady=(0, 10))

        vel_container = tk.Frame(vel_frame, bg='#4a5568')
        vel_container.pack(fill='x', padx=10, pady=10)

        self.vel_entries = {}
        for i, axis in enumerate(['X', 'Y', 'Z']):
            tk.Label(vel_container, text=f"{axis} (mm/s):", bg='#4a5568', fg='white').grid(row=0, column=i * 3, padx=5,
                                                                                           pady=5, sticky='e')

            self.vel_entries[axis] = tk.StringVar(value=str(self.velocity[axis]))
            entry = tk.Entry(vel_container, textvariable=self.vel_entries[axis], width=8,
                             bg='#2d3748', fg='white')
            entry.grid(row=0, column=i * 3 + 1, padx=5, pady=5, sticky='w')
            entry.bind('<Return>', lambda e, ax=axis: self.set_velocity(ax))

            tk.Label(vel_container, text=f"Max: {self.MAX_VELOCITY}", font=('Arial', 8),
                     fg='gray', bg='#4a5568').grid(row=1, column=i * 3 + 1, padx=5, sticky='w')

    def setup_manual_control(self):
        """Manual control interface - simulates MVR() commands"""

        tk.Label(self.manual_frame, text="Manual Control", font=('Arial', 16, 'bold'),
                 bg='#2d3748', fg='white').pack(pady=(0, 10))

        # Step size
        step_frame = tk.Frame(self.manual_frame, bg='#2d3748')
        step_frame.pack(pady=(0, 20))

        tk.Label(step_frame, text="Step Size (mm):", bg='#2d3748', fg='white').pack(side='left')
        self.step_entry = tk.StringVar(value='1.0')
        tk.Entry(step_frame, textvariable=self.step_entry, width=10, bg='#4a5568', fg='white').pack(side='left',
                                                                                                    padx=(5, 0))

        # Direction controls
        controls_frame = tk.Frame(self.manual_frame, bg='#2d3748')
        controls_frame.pack()

        for i, axis in enumerate(['X', 'Y', 'Z']):
            axis_frame = tk.LabelFrame(controls_frame, text=f"{axis}-Axis", bg='#4a5568', fg='white')
            axis_frame.grid(row=0, column=i, padx=20, pady=10, sticky='nsew')

            # Positive direction button
            pos_btn = tk.Button(axis_frame, text=f"+{axis}", bg='#38a169', fg='white',
                                command=lambda ax=axis: self.move_relative(ax, self.get_step_size()))
            pos_btn.pack(pady=5)

            # Current position
            pos_label = tk.Label(axis_frame, text=f"{self.current_pos[axis]:.3f} mm",
                                 bg='#4a5568', fg='white')
            pos_label.pack(pady=5)

            # Negative direction button
            neg_btn = tk.Button(axis_frame, text=f"-{axis}", bg='#e53e3e', fg='white',
                                command=lambda ax=axis: self.move_relative(ax, -self.get_step_size()))
            neg_btn.pack(pady=5)

    def setup_automated_control(self):
        """Automated control interface - simulates Tmotion2.0.py waypoint system"""
        tk.Label(self.automated_frame, text="Automated Sequence", font=('Arial', 16, 'bold'),
                 bg='#2d3748', fg='white').pack(pady=(0, 10))

        # Control buttons
        btn_frame = tk.Frame(self.automated_frame, bg='#2d3748')
        btn_frame.pack(pady=(0, 10))

        self.start_btn = tk.Button(btn_frame, text="Start Sequence", bg='#38a169', fg='white',
                                   command=self.start_automated_sequence)
        self.start_btn.pack(side='left', padx=5)

        self.stop_btn = tk.Button(btn_frame, text="Stop Motion", bg='#e53e3e', fg='white',
                                  command=self.stop_motion, state='disabled')
        self.stop_btn.pack(side='left', padx=5)

        tk.Button(btn_frame, text="Add Waypoint", bg='#3182ce', fg='white',
                  command=self.add_waypoint).pack(side='left', padx=5)

        # Status
        self.status_label = tk.Label(self.automated_frame, text="Ready",
                                     bg='#2d3748', fg='white')
        self.status_label.pack(pady=5)

        # Waypoints table
        self.setup_waypoints_table()

    def setup_waypoints_table(self):
        """Waypoints configuration table"""
        table_frame = tk.Frame(self.automated_frame, bg='#2d3748')
        table_frame.pack(fill='both', expand=True, pady=10)

        # Headers
        headers = ['#', 'X (mm)', 'Y (mm)', 'Z (mm)', 'Hold (s)', 'Remove']
        for i, header in enumerate(headers):
            tk.Label(table_frame, text=header, font=('Arial', 10, 'bold'),
                     bg='#4a5568', fg='white').grid(row=0, column=i, padx=5, pady=5, sticky='ew')

        self.table_frame = table_frame
        self.waypoint_widgets = []
        self.update_waypoints_table()

    def update_waypoints_table(self):
        """Update waypoints table display"""
        # Clear existing widgets
        for widgets in self.waypoint_widgets:
            for widget in widgets:
                widget.destroy()
        self.waypoint_widgets.clear()

        # Create new rows
        for i, wp in enumerate(self.waypoints):
            row_widgets = []
            row = i + 1

            # Index
            label = tk.Label(self.table_frame, text=str(i + 1), bg='#4a5568', fg='white')
            label.grid(row=row, column=0, padx=5, pady=2)
            row_widgets.append(label)

            # X, Y, Z entries
            for j, axis in enumerate(['X', 'Y', 'Z']):
                entry = tk.Entry(self.table_frame, width=8, bg='#2d3748', fg='white')
                entry.insert(0, str(wp[axis]))
                entry.grid(row=row, column=j + 1, padx=5, pady=2)
                entry.bind('<Return>', self.create_waypoint_callback(i, axis))
                row_widgets.append(entry)

            # Hold time
            hold_entry = tk.Entry(self.table_frame, width=6, bg='#2d3748', fg='white')
            hold_entry.insert(0, str(wp['holdTime']))
            hold_entry.grid(row=row, column=4, padx=5, pady=2)
            hold_entry.bind('<Return>', self.create_waypoint_callback(i, 'holdTime'))
            row_widgets.append(hold_entry)

            # Remove button
            remove_btn = tk.Button(self.table_frame, text="Remove", bg='#e53e3e', fg='white',
                                   command=self.create_remove_callback(i))
            remove_btn.grid(row=row, column=5, padx=5, pady=2)
            row_widgets.append(remove_btn)

            self.waypoint_widgets.append(row_widgets)

    def create_waypoint_callback(self, index, field):
        """Create callback function for waypoint updates"""

        def callback(event):
            try:
                value = float(event.widget.get())
                self.waypoints[index][field] = value
            except ValueError:
                pass

        return callback

    def create_remove_callback(self, index):
        """Create callback function for removing waypoints"""

        def callback():
            self.remove_waypoint(index)

        return callback

    def connect_devices(self):
        """Simulate connection to PI controllers"""
        try:
            # This would normally connect to real hardware using:
            # from pipython import GCSDevice
            # device = GCSDevice()
            # device.ConnectUSB(serialnum='025550131')  # X-axis
            # self.pidevices['X'] = device

            # For demonstration, we'll simulate connection
            self.connected = True
            self.conn_status.config(text="Connected (Simulated)", fg='green')
            print("Simulated connection to PI controllers")

        except Exception as e:
            messagebox.showerror("Connection Error", str(e))

    def safe_range(self, axis, target_pos):
        """Apply safe range clamping - from origintools.py safe_range function"""
        min_limit = self.SAFE_RANGES[axis]['min']
        max_limit = self.SAFE_RANGES[axis]['max']

        if target_pos < min_limit:
            print(f"INFO: Target {target_pos} for axis {axis} clamped to {min_limit}")
            return min_limit
        if target_pos > max_limit:
            print(f"INFO: Target {target_pos} for axis {axis} clamped to {max_limit}")
            return max_limit
        return target_pos

    def set_velocity(self, axis):
        """Set velocity for axis - simulates VEL() command"""
        try:
            new_vel = float(self.vel_entries[axis].get())
            if new_vel > self.MAX_VELOCITY:
                messagebox.showwarning("Velocity Warning",
                                       f"Velocity {new_vel} exceeds maximum {self.MAX_VELOCITY} mm/s")
                return
            if new_vel <= 0:
                messagebox.showwarning("Velocity Warning", "Velocity must be positive")
                return

            self.velocity[axis] = new_vel

            # If connected to real hardware, call:
            # self.pidevices[axis].VEL(self.pidevices[axis].axes[0], new_vel)
            print(f"VEL({axis}, {new_vel:.2f})")  # Simulates pipython VEL() command

        except ValueError:
            messagebox.showerror("Error", "Invalid velocity value")

    def move_to_position(self, axis, target):
        """Move to absolute position - simulates MOV() command"""
        safe_pos = self.safe_range(axis, target)
        self.current_pos[axis] = safe_pos

        # If connected to real hardware, call:
        # self.pidevices[axis].MOV(self.pidevices[axis].axes[0], safe_pos)
        print(f"MOV({axis}, {safe_pos:.3f})")  # Simulates pipython MOV() command

        self.update_position_display()

    def move_relative(self, axis, distance):
        """Move relative distance - simulates MVR() command"""
        new_pos = self.current_pos[axis] + distance
        self.move_to_position(axis, new_pos)
        print(f"MVR({axis}, {distance:.3f})")  # Simulates pipython MVR() command

    def get_step_size(self):
        """Get current step size for manual moves"""
        try:
            return float(self.step_entry.get())
        except ValueError:
            return 1.0

    def update_position_display(self):
        """Update position labels - simulates qPOS() readout"""
        for axis in ['X', 'Y', 'Z']:
            self.pos_labels[axis].config(text=f"{self.current_pos[axis]:.3f}")

    def mode_changed(self):
        """Handle mode selection change"""
        if self.mode.get() == 'manual':
            self.show_manual_control()
        else:
            self.show_automated_control()

    def show_manual_control(self):
        """Show manual control interface"""
        self.automated_frame.pack_forget()
        self.manual_frame.pack(fill='both', expand=True)

    def show_automated_control(self):
        """Show automated control interface"""
        self.manual_frame.pack_forget()
        self.automated_frame.pack(fill='both', expand=True)

    def start_automated_sequence(self):
        """Start automated waypoint sequence - simulates Tmotion2.0.py logic"""
        if not self.waypoints:
            messagebox.showwarning("Error", "No waypoints defined")
            return

        self.is_running = True
        self.start_btn.config(state='disabled')
        self.stop_btn.config(state='normal')

        # Set velocity for all axes before motion (simulates VEL() calls)
        for axis in ['X', 'Y', 'Z']:
            print(f"VEL({axis}, {self.velocity[axis]:.2f})")

        # Start sequence in separate thread
        threading.Thread(target=self.run_sequence, daemon=True).start()

    def run_sequence(self):
        """Execute waypoint sequence"""
        for i, waypoint in enumerate(self.waypoints):
            if not self.is_running:
                break

            self.root.after(0, lambda idx=i: self.status_label.config(
                text=f"Executing waypoint {idx + 1}/{len(self.waypoints)}"))

            # Move to waypoint position (simulates MOV() commands)
            for axis in ['X', 'Y', 'Z']:
                if axis in waypoint:
                    self.root.after(0, lambda ax=axis, pos=waypoint[axis]: self.move_to_position(ax, pos))

            # Hold time
            time.sleep(waypoint['holdTime'])

        # Sequence complete
        self.root.after(0, self.sequence_complete)

    def stop_motion(self):
        """Stop motion sequence - simulates pitools.stopall()"""
        self.is_running = False
        print("StopAll()")  # Simulates pipython StopAll() command
        self.sequence_complete()

    def sequence_complete(self):
        """Reset UI after sequence completion"""
        self.is_running = False
        self.start_btn.config(state='normal')
        self.stop_btn.config(state='disabled')
        self.status_label.config(text="Sequence Complete")

    def add_waypoint(self):
        """Add new waypoint"""
        self.waypoints.append({'X': 50.0, 'Y': 50.0, 'Z': 50.0, 'holdTime': 1.0})
        self.update_waypoints_table()

    def remove_waypoint(self, index):
        """Remove waypoint"""
        if len(self.waypoints) > 1:
            self.waypoints.pop(index)
            self.update_waypoints_table()


def main():
    """Main function to launch the GUI"""
    root = tk.Tk()
    app = PIStageGUI(root)
    root.mainloop()


if __name__ == '__main__':
    main()