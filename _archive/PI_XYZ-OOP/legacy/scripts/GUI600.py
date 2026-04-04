#!/usr/bin/python
# -*- coding: utf-8 -*-
"""
PI Stage Control GUI using PySide6
Run this file directly in PyCharm to launch the GUI
"""

import sys
from PySide6.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout,
                               QHBoxLayout, QGridLayout, QLabel, QPushButton,
                               QLineEdit, QRadioButton, QGroupBox, QTableWidget,
                               QTableWidgetItem, QHeaderView, QMessageBox)
from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QFont
import threading
import time


class PIStageGUI(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("PI Stage Control System")
        self.setGeometry(100, 100, 1200, 800)

        # Stage parameters from project knowledge
        self.current_pos = {'X': 0.0, 'Y': 0.0, 'Z': 0.0}
        self.velocity = {'X': 10.0, 'Y': 10.0, 'Z': 10.0}

        # Safe ranges from Tmotion2.0.py
        self.SAFE_RANGES = {
            'X': {'min': 5.0, 'max': 200.0},
            'Y': {'min': 0.0, 'max': 200.0},
            'Z': {'min': 15.0, 'max': 200.0}
        }
        self.MAX_VELOCITY = 20.0  # VT-80 limit

        self.mode = 'manual'
        self.is_running = False
        self.waypoints = [
            {'X': 10.0, 'Y': 5.0, 'Z': 20.0, 'holdTime': 1.0},
            {'X': 25.0, 'Y': 15.0, 'Z': 30.0, 'holdTime': 2.0}
        ]

        self.setup_ui()
        self.setup_timer()

    def setup_ui(self):
        central_widget = QWidget()
        self.setCentralWidget(central_widget)

        # Apply dark theme stylesheet
        self.setStyleSheet("""
            QMainWindow { background-color: #2d3748; }
            QGroupBox { 
                background-color: #4a5568; 
                border: 2px solid #718096;
                border-radius: 8px;
                margin: 5px;
                padding-top: 15px;
                color: white;
                font-weight: bold;
            }
            QLabel { color: white; background-color: transparent; }
            QPushButton { 
                background-color: #3182ce; 
                color: white; 
                border: none; 
                padding: 8px;
                border-radius: 4px;
                font-weight: bold;
            }
            QPushButton:hover { background-color: #2c5aa0; }
            QPushButton:disabled { background-color: #4a5568; color: #a0aec0; }
            QLineEdit { 
                background-color: #2d3748; 
                color: white; 
                border: 2px solid #4a5568;
                padding: 5px;
                border-radius: 4px;
            }
            QRadioButton { color: white; }
            QTableWidget { 
                background-color: #2d3748;
                color: white;
                gridline-color: #4a5568;
            }
            QHeaderView::section {
                background-color: #4a5568;
                color: white;
                padding: 8px;
                border: 1px solid #2d3748;
            }
        """)

        layout = QVBoxLayout(central_widget)

        # Title
        title = QLabel("PI Stage Control System")
        title.setAlignment(Qt.AlignCenter)
        title.setFont(QFont("Arial", 24, QFont.Bold))
        layout.addWidget(title)

        # Position display
        self.setup_position_group(layout)

        # Mode selection
        self.setup_mode_group(layout)

        # Velocity settings
        self.setup_velocity_group(layout)

        # Control area
        self.setup_control_area(layout)

    def setup_position_group(self, layout):
        """Current position display - simulates qPOS() readout"""
        pos_group = QGroupBox("Current Position")
        pos_layout = QHBoxLayout(pos_group)

        self.pos_labels = {}
        for axis in ['X', 'Y', 'Z']:
            axis_widget = QWidget()
            axis_layout = QVBoxLayout(axis_widget)

            # Axis name
            axis_label = QLabel(f"{axis}-Axis")
            axis_label.setAlignment(Qt.AlignCenter)
            axis_label.setFont(QFont("Arial", 14, QFont.Bold))
            axis_layout.addWidget(axis_label)

            # Position value
            self.pos_labels[axis] = QLabel("0.000")
            self.pos_labels[axis].setAlignment(Qt.AlignCenter)
            self.pos_labels[axis].setFont(QFont("Arial", 20, QFont.Bold))
            self.pos_labels[axis].setStyleSheet("color: #00bcd4;")
            axis_layout.addWidget(self.pos_labels[axis])

            # Units
            units_label = QLabel("mm")
            units_label.setAlignment(Qt.AlignCenter)
            axis_layout.addWidget(units_label)

            # Range info
            range_text = f"[{self.SAFE_RANGES[axis]['min']}-{self.SAFE_RANGES[axis]['max']}]"
            range_label = QLabel(range_text)
            range_label.setAlignment(Qt.AlignCenter)
            range_label.setStyleSheet("color: #a0aec0; font-size: 10px;")
            axis_layout.addWidget(range_label)

            pos_layout.addWidget(axis_widget)

        layout.addWidget(pos_group)

    def setup_mode_group(self, layout):
        """Mode selection"""
        mode_group = QGroupBox("Control Mode")
        mode_layout = QHBoxLayout(mode_group)

        self.manual_radio = QRadioButton("Manual Mode")
        self.manual_radio.setChecked(True)
        self.manual_radio.toggled.connect(self.mode_changed)
        mode_layout.addWidget(self.manual_radio)

        self.auto_radio = QRadioButton("Automated Mode")
        self.auto_radio.toggled.connect(self.mode_changed)
        mode_layout.addWidget(self.auto_radio)

        layout.addWidget(mode_group)

    def setup_velocity_group(self, layout):
        """Velocity settings - simulates VEL() commands"""
        vel_group = QGroupBox("Velocity Settings")
        vel_layout = QHBoxLayout(vel_group)

        self.vel_entries = {}
        for axis in ['X', 'Y', 'Z']:
            axis_widget = QWidget()
            axis_layout = QVBoxLayout(axis_widget)

            label = QLabel(f"{axis}-Axis (mm/s)")
            label.setAlignment(Qt.AlignCenter)
            axis_layout.addWidget(label)

            self.vel_entries[axis] = QLineEdit(str(self.velocity[axis]))
            self.vel_entries[axis].setAlignment(Qt.AlignCenter)
            self.vel_entries[axis].returnPressed.connect(lambda ax=axis: self.set_velocity(ax))
            axis_layout.addWidget(self.vel_entries[axis])

            max_label = QLabel(f"Max: {self.MAX_VELOCITY}")
            max_label.setAlignment(Qt.AlignCenter)
            max_label.setStyleSheet("color: #a0aec0; font-size: 10px;")
            axis_layout.addWidget(max_label)

            vel_layout.addWidget(axis_widget)

        layout.addWidget(vel_group)

    def setup_control_area(self, layout):
        """Setup control area for manual/automated modes"""
        self.control_widget = QWidget()
        self.control_layout = QVBoxLayout(self.control_widget)

        # Manual control
        self.setup_manual_control()

        # Automated control
        self.setup_automated_control()

        layout.addWidget(self.control_widget)
        self.show_manual_control()

    def setup_manual_control(self):
        """Manual control interface - simulates MVR() commands"""
        self.manual_group = QGroupBox("Manual Control")
        manual_layout = QVBoxLayout(self.manual_group)

        # Step size
        step_layout = QHBoxLayout()
        step_layout.addWidget(QLabel("Step Size (mm):"))
        self.step_entry = QLineEdit("1.0")
        self.step_entry.setMaximumWidth(100)
        step_layout.addWidget(self.step_entry)
        step_layout.addStretch()
        manual_layout.addLayout(step_layout)

        # Direction controls
        controls_layout = QHBoxLayout()
        for axis in ['X', 'Y', 'Z']:
            axis_group = QGroupBox(f"{axis}-Axis")
            axis_layout = QVBoxLayout(axis_group)

            # Positive button
            pos_btn = QPushButton(f"+{axis}")
            pos_btn.setStyleSheet("QPushButton { background-color: #38a169; }")
            pos_btn.clicked.connect(lambda checked, ax=axis: self.move_relative(ax, self.get_step_size()))
            axis_layout.addWidget(pos_btn)

            # Position display
            pos_display = QLabel(f"{self.current_pos[axis]:.3f} mm")
            pos_display.setAlignment(Qt.AlignCenter)
            axis_layout.addWidget(pos_display)

            # Negative button
            neg_btn = QPushButton(f"-{axis}")
            neg_btn.setStyleSheet("QPushButton { background-color: #e53e3e; }")
            neg_btn.clicked.connect(lambda checked, ax=axis: self.move_relative(ax, -self.get_step_size()))
            axis_layout.addWidget(neg_btn)

            controls_layout.addWidget(axis_group)

        manual_layout.addLayout(controls_layout)

    def setup_automated_control(self):
        """Automated control interface - simulates Tmotion2.0.py waypoint system"""
        self.auto_group = QGroupBox("Automated Sequence")
        auto_layout = QVBoxLayout(self.auto_group)

        # Control buttons
        btn_layout = QHBoxLayout()

        self.start_btn = QPushButton("Start Sequence")
        self.start_btn.setStyleSheet("QPushButton { background-color: #38a169; }")
        self.start_btn.clicked.connect(self.start_automated_sequence)
        btn_layout.addWidget(self.start_btn)

        self.stop_btn = QPushButton("Stop Motion")
        self.stop_btn.setStyleSheet("QPushButton { background-color: #e53e3e; }")
        self.stop_btn.setEnabled(False)
        self.stop_btn.clicked.connect(self.stop_motion)
        btn_layout.addWidget(self.stop_btn)

        add_btn = QPushButton("Add Waypoint")
        add_btn.clicked.connect(self.add_waypoint)
        btn_layout.addWidget(add_btn)

        btn_layout.addStretch()
        auto_layout.addLayout(btn_layout)

        # Status
        self.status_label = QLabel("Ready")
        self.status_label.setAlignment(Qt.AlignCenter)
        auto_layout.addWidget(self.status_label)

        # Waypoints table
        self.waypoint_table = QTableWidget()
        self.waypoint_table.setColumnCount(5)
        self.waypoint_table.setHorizontalHeaderLabels(['X (mm)', 'Y (mm)', 'Z (mm)', 'Hold (s)', 'Remove'])
        self.waypoint_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        auto_layout.addWidget(self.waypoint_table)

        self.update_waypoint_table()

    def setup_timer(self):
        """Timer for position updates"""
        self.timer = QTimer()
        self.timer.timeout.connect(self.update_position_display)
        self.timer.start(100)  # Update every 100ms

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
            new_vel = float(self.vel_entries[axis].text())
            if new_vel > self.MAX_VELOCITY:
                QMessageBox.warning(self, "Velocity Warning",
                                    f"Velocity {new_vel} exceeds maximum {self.MAX_VELOCITY} mm/s")
                return
            if new_vel <= 0:
                QMessageBox.warning(self, "Velocity Warning", "Velocity must be positive")
                return

            self.velocity[axis] = new_vel
            print(f"VEL({axis}, {new_vel:.2f})")  # Simulates pipython VEL() command

        except ValueError:
            QMessageBox.critical(self, "Error", "Invalid velocity value")

    def move_to_position(self, axis, target):
        """Move to absolute position - simulates MOV() command"""
        safe_pos = self.safe_range(axis, target)
        self.current_pos[axis] = safe_pos
        print(f"MOV({axis}, {safe_pos:.3f})")  # Simulates pipython MOV() command

    def move_relative(self, axis, distance):
        """Move relative distance - simulates MVR() command"""
        new_pos = self.current_pos[axis] + distance
        self.move_to_position(axis, new_pos)
        print(f"MVR({axis}, {distance:.3f})")  # Simulates pipython MVR() command

    def get_step_size(self):
        """Get current step size for manual moves"""
        try:
            return float(self.step_entry.text())
        except ValueError:
            return 1.0

    def update_position_display(self):
        """Update position labels - simulates qPOS() readout"""
        for axis in ['X', 'Y', 'Z']:
            self.pos_labels[axis].setText(f"{self.current_pos[axis]:.3f}")

    def mode_changed(self):
        """Handle mode selection change"""
        if self.manual_radio.isChecked():
            self.mode = 'manual'
            self.show_manual_control()
        else:
            self.mode = 'automated'
            self.show_automated_control()

    def show_manual_control(self):
        """Show manual control interface"""
        self.auto_group.hide()
        self.manual_group.show()

    def show_automated_control(self):
        """Show automated control interface"""
        self.manual_group.hide()
        self.auto_group.show()

    def start_automated_sequence(self):
        """Start automated waypoint sequence - simulates Tmotion2.0.py logic"""
        if not self.waypoints:
            QMessageBox.warning(self, "Error", "No waypoints defined")
            return

        self.is_running = True
        self.start_btn.setEnabled(False)
        self.stop_btn.setEnabled(True)

        # Set velocity for all axes (simulates VEL() calls)
        for axis in ['X', 'Y', 'Z']:
            print(f"VEL({axis}, {self.velocity[axis]:.2f})")

        # Start sequence in separate thread
        threading.Thread(target=self.run_sequence, daemon=True).start()

    def run_sequence(self):
        """Execute waypoint sequence"""
        for i, waypoint in enumerate(self.waypoints):
            if not self.is_running:
                break

            self.status_label.setText(f"Executing waypoint {i + 1}/{len(self.waypoints)}")

            # Move to waypoint (simulates MOV() commands)
            for axis in ['X', 'Y', 'Z']:
                if axis in waypoint:
                    self.move_to_position(axis, waypoint[axis])

            # Hold time
            time.sleep(waypoint['holdTime'])

        self.sequence_complete()

    def stop_motion(self):
        """Stop motion sequence - simulates pitools.stopall()"""
        self.is_running = False
        print("StopAll()")  # Simulates pipython StopAll() command
        self.sequence_complete()

    def sequence_complete(self):
        """Reset UI after sequence completion"""
        self.is_running = False
        self.start_btn.setEnabled(True)
        self.stop_btn.setEnabled(False)
        self.status_label.setText("Sequence Complete")

    def update_waypoint_table(self):
        """Update waypoints table display"""
        self.waypoint_table.setRowCount(len(self.waypoints))

        for i, wp in enumerate(self.waypoints):
            # X, Y, Z positions
            for j, axis in enumerate(['X', 'Y', 'Z']):
                item = QTableWidgetItem(str(wp[axis]))
                self.waypoint_table.setItem(i, j, item)

            # Hold time
            hold_item = QTableWidgetItem(str(wp['holdTime']))
            self.waypoint_table.setItem(i, 3, hold_item)

            # Remove button
            remove_btn = QPushButton("Remove")
            remove_btn.setStyleSheet("QPushButton { background-color: #e53e3e; }")
            remove_btn.clicked.connect(lambda checked, idx=i: self.remove_waypoint(idx))
            self.waypoint_table.setCellWidget(i, 4, remove_btn)

    def add_waypoint(self):
        """Add new waypoint"""
        self.waypoints.append({'X': 50.0, 'Y': 50.0, 'Z': 50.0, 'holdTime': 1.0})
        self.update_waypoint_table()

    def remove_waypoint(self, index):
        """Remove waypoint"""
        if len(self.waypoints) > 1:
            self.waypoints.pop(index)
            self.update_waypoint_table()


def main():
    """Main function to launch the GUI"""
    app = QApplication(sys.argv)

    # Set application style
    app.setStyle('Fusion')

    window = PIStageGUI()
    window.show()

    sys.exit(app.exec())


if __name__ == '__main__':
    main()