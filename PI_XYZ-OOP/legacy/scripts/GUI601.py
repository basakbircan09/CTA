#!/usr/bin/python
# -*- coding: utf-8 -*-
"""
Modern PI Stage Control GUI using PySide6
"""

import sys
from PySide6.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout,
                               QHBoxLayout, QGridLayout, QLabel, QPushButton,
                               QLineEdit, QRadioButton, QFrame, QTableWidget,
                               QTableWidgetItem, QHeaderView, QSpacerItem,
                               QSizePolicy, QStackedWidget, QSlider, QSpinBox,
                               QDoubleSpinBox)
from PySide6.QtCore import Qt, QTimer, QPropertyAnimation, QEasingCurve, QRect
from PySide6.QtGui import QFont, QPalette, QColor
import threading
import time


class ModernCard(QFrame):
    def __init__(self, title="", parent=None):
        super().__init__(parent)
        self.setFrameStyle(QFrame.Box)
        # Modern theme with your palette
        self.setStyleSheet(f"""
            QMainWindow {{
                background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
                    stop:0 #0D1D55, stop:1 #38688C);
            }}

            QLabel {{
                color: #FFFFDD;
                background: transparent;
            }}

            QPushButton {{
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                    stop:0 #63B3C2, stop:1 #38688C);
                color: #FFFFEC;
                border: none;
                padding: 10px 20px;
                border-radius: 8px;
                font-weight: 600;
                font-size: 13px;
            }}
            QPushButton:hover {{
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                    stop:0 #B1D9D0, stop:1 #63B3C2);
            }}
            QPushButton:disabled {{
                background: #4a5568;
                color: #999999;
            }}

            QPushButton.green {{
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                    stop:0 #63B3C2, stop:1 #38a169);
                color: #FFFFDD;
            }}
            QPushButton.red {{
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                    stop:0 #f56565, stop:1 #e53e3e);
                color: #FFFFDD;
            }}

            QLineEdit, QSpinBox, QDoubleSpinBox {{
                background-color: rgba(99, 179, 194, 0.2);
                color: #FFFFDD;
                border: 2px solid rgba(255, 255, 255, 0.2);
                border-radius: 6px;
                padding: 6px;
                font-size: 13px;
            }}
            QLineEdit:focus, QSpinBox:focus, QDoubleSpinBox:focus {{
                border-color: #B1D9D0;
            }}

            QRadioButton {{
                color: #FFFFEC;
                font-size: 14px;
                font-weight: 500;
            }}
            QRadioButton::indicator:checked {{
                background-color: #63B3C2;
                border-color: #63B3C2;
            }}

            QTableWidget {{
                background-color: rgba(56, 104, 140, 0.6);
                color: #FFFFDD;
                border: none;
                border-radius: 8px;
            }}
            QHeaderView::section {{
                background-color: #38688C;
                color: #FFFFEC;
                padding: 8px;
                font-weight: 600;
            }}
        """)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 15, 20, 15)

        if title:
            title_label = QLabel(title)
            title_label.setFont(QFont("Segoe UI", 14, QFont.Bold))
            title_label.setStyleSheet("color: #e2e8f0; margin-bottom: 10px;")
            layout.addWidget(title_label)


class PIStageGUI(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("PI Stage Control System")
        self.setGeometry(100, 100, 1400, 900)

        # Force the window to obey the stylesheet for background
        self.setAutoFillBackground(True)
        self.setStyleSheet("""
                    QMainWindow {
                        background: qlineargradient(
                            x1:0, y1:0, x2:1, y2:1,
                            stop:0 #0D1D55,
                            stop:1 #38688C
                        );
                    }
                """)

        # Stage parameters
        self.current_pos = {'X': 0.0, 'Y': 0.0, 'Z': 0.0}
        self.velocity = {'X': 10.0, 'Y': 10.0, 'Z': 10.0}

        # CUSTOMIZABLE: Safe ranges and velocity limits (modify these values)
        self.SAFE_RANGES = {
            'X': {'min': 5.0, 'max': 200.0},  # X-axis travel range in mm
            'Y': {'min': 0.0, 'max': 200.0},  # Y-axis travel range in mm
            'Z': {'min': 15.0, 'max': 200.0}  # Z-axis travel range in mm
        }
        self.MAX_VELOCITY = 20.0  # CUSTOMIZABLE: Maximum velocity in mm/s

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

        # Switch to horizontal layout for better monitor use
        main_layout = QHBoxLayout(central_widget)
        main_layout.setSpacing(20)
        main_layout.setContentsMargins(20, 20, 20, 20)

        # === Left column ===
        left_col = QVBoxLayout()
        left_col.setSpacing(20)

        # Title
        title = QLabel("PI Stage Control System")
        title.setAlignment(Qt.AlignCenter)
        title.setFont(QFont("Segoe UI", 24, QFont.Bold))
        title.setStyleSheet("""
            color: #e2e8f0;
            margin: 10px;
            text-shadow: 0 0 15px rgba(66, 153, 225, 0.5);
        """)
        left_col.addWidget(title)

        # Position + Velocity on left
        self.setup_position_display(left_col)
        self.setup_velocity_panel(left_col)

        # === Right column ===
        right_col = QVBoxLayout()
        right_col.setSpacing(20)

        # Mode switcher + controls on right
        self.setup_mode_switcher(right_col)
        self.setup_control_stack(right_col)

        # Add columns to main horizontal layout
        main_layout.addLayout(left_col, 1)
        main_layout.addLayout(right_col, 2)

    def setup_position_display(self, layout):
        """Modern position display - simulates qPOS() readout"""
        pos_card = ModernCard("Current Position")
        pos_layout = pos_card.layout()

        grid_widget = QWidget()
        grid_layout = QGridLayout(grid_widget)
        grid_layout.setSpacing(30)

        self.pos_labels = {}
        for i, axis in enumerate(['X', 'Y', 'Z']):
            # Axis container
            axis_frame = QFrame()
            axis_frame.setStyleSheet("""
                QFrame {
                    background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
                        stop:0 rgba(66, 153, 225, 0.1), stop:1 rgba(49, 130, 206, 0.1));
                    border-radius: 12px;
                    padding: 15px;
                }
            """)
            axis_layout = QVBoxLayout(axis_frame)

            # Axis label
            axis_label = QLabel(f"{axis}-Axis")
            axis_label.setAlignment(Qt.AlignCenter)
            axis_label.setFont(QFont("Segoe UI", 16, QFont.Bold))
            axis_label.setStyleSheet("color: #4299e1; margin-bottom: 5px;")
            axis_layout.addWidget(axis_label)

            # Position value with glow
            self.pos_labels[axis] = QLabel("0.000")
            self.pos_labels[axis].setAlignment(Qt.AlignCenter)
            self.pos_labels[axis].setFont(QFont("Segoe UI", 28, QFont.Bold))
            self.pos_labels[axis].setStyleSheet("""
                color: #00d4aa;
                margin: 10px;
                text-shadow: 0 0 15px rgba(0, 212, 170, 0.6);
            """)
            axis_layout.addWidget(self.pos_labels[axis])

            # Units
            units = QLabel("mm")
            units.setAlignment(Qt.AlignCenter)
            units.setStyleSheet("color: #a0aec0; font-size: 14px; margin-bottom: 5px;")
            axis_layout.addWidget(units)

            # Range
            range_text = f"Range: {self.SAFE_RANGES[axis]['min']}-{self.SAFE_RANGES[axis]['max']}"
            range_label = QLabel(range_text)
            range_label.setAlignment(Qt.AlignCenter)
            range_label.setStyleSheet("color: #718096; font-size: 11px;")
            axis_layout.addWidget(range_label)

            grid_layout.addWidget(axis_frame, 0, i)

        pos_layout.addWidget(grid_widget)
        layout.addWidget(pos_card)

    def setup_mode_switcher(self, layout):
        """Modern mode switcher"""
        mode_card = ModernCard("Control Mode")
        mode_layout = mode_card.layout()

        switch_layout = QHBoxLayout()
        switch_layout.addStretch()

        self.manual_radio = QRadioButton("Manual Control")
        self.manual_radio.setChecked(True)
        self.manual_radio.toggled.connect(self.mode_changed)
        switch_layout.addWidget(self.manual_radio)

        switch_layout.addSpacing(50)

        self.auto_radio = QRadioButton("Automated Sequence")
        self.auto_radio.toggled.connect(self.mode_changed)
        switch_layout.addWidget(self.auto_radio)

        switch_layout.addStretch()
        mode_layout.addLayout(switch_layout)

        layout.addWidget(mode_card)

    def setup_velocity_panel(self, layout):
        """Modern velocity controls - simulates VEL() commands"""
        vel_card = ModernCard("Velocity Settings")
        vel_layout = vel_card.layout()

        grid_widget = QWidget()
        grid_layout = QGridLayout(grid_widget)

        self.vel_spinboxes = {}
        for i, axis in enumerate(['X', 'Y', 'Z']):
            # Label
            label = QLabel(f"{axis}-Axis")
            label.setAlignment(Qt.AlignCenter)
            label.setFont(QFont("Segoe UI", 12, QFont.Bold))
            grid_layout.addWidget(label, 0, i)

            # Spinbox
            self.vel_spinboxes[axis] = QDoubleSpinBox()
            self.vel_spinboxes[axis].setRange(0.1, self.MAX_VELOCITY)
            self.vel_spinboxes[axis].setValue(self.velocity[axis])
            self.vel_spinboxes[axis].setSuffix(" mm/s")
            self.vel_spinboxes[axis].setDecimals(1)
            self.vel_spinboxes[axis].valueChanged.connect(lambda v, ax=axis: self.set_velocity(ax, v))
            grid_layout.addWidget(self.vel_spinboxes[axis], 1, i)

            # Max indicator
            max_label = QLabel(f"Max: {self.MAX_VELOCITY} mm/s")
            max_label.setAlignment(Qt.AlignCenter)
            max_label.setStyleSheet("color: #a0aec0; font-size: 10px;")
            grid_layout.addWidget(max_label, 2, i)

        vel_layout.addWidget(grid_widget)
        layout.addWidget(vel_card)

    def setup_control_stack(self, layout):
        """Stacked widget for manual/automated controls"""
        self.control_stack = QStackedWidget()

        # Manual control page
        self.setup_manual_page()

        # Automated control page
        self.setup_automated_page()

        layout.addWidget(self.control_stack)

    def setup_manual_page(self):
        """Modern manual control - simulates MVR() commands"""
        manual_page = QWidget()
        page_layout = QVBoxLayout(manual_page)

        manual_card = ModernCard("Manual Control")
        manual_layout = manual_card.layout()

        # Step size with slider
        step_container = QWidget()
        step_layout = QHBoxLayout(step_container)

        step_layout.addWidget(QLabel("Step Size:"))

        self.step_spinbox = QDoubleSpinBox()
        self.step_spinbox.setRange(0.1, 50.0)
        self.step_spinbox.setValue(1.0)
        self.step_spinbox.setSuffix(" mm")
        self.step_spinbox.setDecimals(1)
        step_layout.addWidget(self.step_spinbox)

        step_layout.addStretch()
        manual_layout.addWidget(step_container)

        # Direction controls grid
        controls_widget = QWidget()
        controls_layout = QGridLayout(controls_widget)
        controls_layout.setSpacing(25)

        self.manual_pos_labels = {}
        for i, axis in enumerate(['X', 'Y', 'Z']):
            # Axis group
            axis_container = QFrame()
            axis_container.setStyleSheet("""
                QFrame {
                    background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
                        stop:0 rgba(56, 161, 105, 0.1), stop:1 rgba(72, 187, 120, 0.1));
                    border-radius: 10px;
                    padding: 20px;
                }
            """)
            axis_layout = QVBoxLayout(axis_container)

            # Axis title
            axis_title = QLabel(f"{axis}-Axis")
            axis_title.setAlignment(Qt.AlignCenter)
            axis_title.setFont(QFont("Segoe UI", 14, QFont.Bold))
            axis_title.setStyleSheet("color: #68d391; margin-bottom: 10px;")
            axis_layout.addWidget(axis_title)

            # Positive button
            pos_btn = QPushButton(f"+ Move")
            pos_btn.setProperty("class", "green")
            pos_btn.clicked.connect(lambda checked, ax=axis: self.move_relative(ax, self.step_spinbox.value()))
            axis_layout.addWidget(pos_btn)

            # Current position
            self.manual_pos_labels[axis] = QLabel(f"{self.current_pos[axis]:.3f} mm")
            self.manual_pos_labels[axis].setAlignment(Qt.AlignCenter)
            self.manual_pos_labels[axis].setFont(QFont("Segoe UI", 16, QFont.Bold))
            self.manual_pos_labels[axis].setStyleSheet("color: #00d4aa; margin: 10px;")
            axis_layout.addWidget(self.manual_pos_labels[axis])

            # Negative button
            neg_btn = QPushButton(f"- Move")
            neg_btn.setProperty("class", "red")
            neg_btn.clicked.connect(lambda checked, ax=axis: self.move_relative(ax, -self.step_spinbox.value()))
            axis_layout.addWidget(neg_btn)

            controls_layout.addWidget(axis_container, 0, i)

        manual_layout.addWidget(controls_widget)
        page_layout.addWidget(manual_card)

        self.control_stack.addWidget(manual_page)

    def setup_automated_page(self):
        """Modern automated control - simulates Tmotion2.0.py waypoint system"""
        auto_page = QWidget()
        page_layout = QVBoxLayout(auto_page)

        auto_card = ModernCard("Automated Sequence")
        auto_layout = auto_card.layout()

        # Control buttons
        btn_container = QWidget()
        btn_layout = QHBoxLayout(btn_container)

        self.start_btn = QPushButton("▶ Start Sequence")
        self.start_btn.setProperty("class", "green")
        self.start_btn.clicked.connect(self.start_automated_sequence)
        btn_layout.addWidget(self.start_btn)

        self.stop_btn = QPushButton("⏹ Stop Motion")
        self.stop_btn.setProperty("class", "red")
        self.stop_btn.setEnabled(False)
        self.stop_btn.clicked.connect(self.stop_motion)
        btn_layout.addWidget(self.stop_btn)

        add_btn = QPushButton("+ Add Waypoint")
        add_btn.clicked.connect(self.add_waypoint)
        btn_layout.addWidget(add_btn)

        btn_layout.addStretch()
        auto_layout.addWidget(btn_container)

        # Status indicator
        self.status_label = QLabel("Ready")
        self.status_label.setAlignment(Qt.AlignCenter)
        self.status_label.setFont(QFont("Segoe UI", 14, QFont.Bold))
        self.status_label.setStyleSheet("""
            color: #68d391;
            background: rgba(56, 161, 105, 0.2);
            padding: 10px;
            border-radius: 6px;
            margin: 10px 0;
        """)
        auto_layout.addWidget(self.status_label)

        # Modern waypoints table
        self.waypoint_table = QTableWidget()
        self.waypoint_table.setColumnCount(5)
        self.waypoint_table.setHorizontalHeaderLabels(['X (mm)', 'Y (mm)', 'Z (mm)', 'Hold (s)', 'Action'])
        self.waypoint_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.waypoint_table.setAlternatingRowColors(True)
        self.waypoint_table.setSelectionBehavior(QTableWidget.SelectRows)
        auto_layout.addWidget(self.waypoint_table)

        self.update_waypoint_table()
        page_layout.addWidget(auto_card)

        self.control_stack.addWidget(auto_page)

    def setup_timer(self):
        """Timer for position updates"""
        self.timer = QTimer()
        self.timer.timeout.connect(self.update_position_display)
        self.timer.start(100)

    def safe_range(self, axis, target_pos):
        """Apply safe range clamping - from origintools.py"""
        min_limit = self.SAFE_RANGES[axis]['min']
        max_limit = self.SAFE_RANGES[axis]['max']

        if target_pos < min_limit:
            print(f"INFO: Target {target_pos} for axis {axis} clamped to {min_limit}")
            return min_limit
        if target_pos > max_limit:
            print(f"INFO: Target {target_pos} for axis {axis} clamped to {max_limit}")
            return max_limit
        return target_pos

    def set_velocity(self, axis, value):
        """Set velocity - simulates VEL() command"""
        self.velocity[axis] = value
        print(f"VEL({axis}, {value:.2f})")

    def move_to_position(self, axis, target):
        """Move to absolute position - simulates MOV() command"""
        safe_pos = self.safe_range(axis, target)
        self.current_pos[axis] = safe_pos
        print(f"MOV({axis}, {safe_pos:.3f})")

    def move_relative(self, axis, distance):
        """Move relative - simulates MVR() command"""
        new_pos = self.current_pos[axis] + distance
        self.move_to_position(axis, new_pos)
        print(f"MVR({axis}, {distance:.3f})")

    def update_position_display(self):
        """Update position labels - simulates qPOS() readout"""
        for axis in ['X', 'Y', 'Z']:
            self.pos_labels[axis].setText(f"{self.current_pos[axis]:.3f}")
            if hasattr(self, 'manual_pos_labels'):
                self.manual_pos_labels[axis].setText(f"{self.current_pos[axis]:.3f} mm")

    def mode_changed(self):
        """Handle mode selection"""
        if self.manual_radio.isChecked():
            self.control_stack.setCurrentIndex(0)
        else:
            self.control_stack.setCurrentIndex(1)

    def start_automated_sequence(self):
        """Start sequence - simulates Tmotion2.0.py logic"""
        self.is_running = True
        self.start_btn.setEnabled(False)
        self.stop_btn.setEnabled(True)

        for axis in ['X', 'Y', 'Z']:
            print(f"VEL({axis}, {self.velocity[axis]:.2f})")

        threading.Thread(target=self.run_sequence, daemon=True).start()

    def run_sequence(self):
        """Execute waypoint sequence"""
        for i, waypoint in enumerate(self.waypoints):
            if not self.is_running:
                break

            self.status_label.setText(f"Executing waypoint {i + 1}/{len(self.waypoints)}")

            for axis in ['X', 'Y', 'Z']:
                if axis in waypoint:
                    self.move_to_position(axis, waypoint[axis])

            time.sleep(waypoint['holdTime'])

        self.sequence_complete()

    def stop_motion(self):
        """Stop motion - simulates pitools.stopall()"""
        self.is_running = False
        print("StopAll()")
        self.sequence_complete()

    def sequence_complete(self):
        """Reset after sequence"""
        self.is_running = False
        self.start_btn.setEnabled(True)
        self.stop_btn.setEnabled(False)
        self.status_label.setText("Sequence Complete")

    def update_waypoint_table(self):
        """Update waypoints table"""
        self.waypoint_table.setRowCount(len(self.waypoints))

        for i, wp in enumerate(self.waypoints):
            # Position values
            for j, axis in enumerate(['X', 'Y', 'Z']):
                spinbox = QDoubleSpinBox()
                spinbox.setRange(self.SAFE_RANGES[axis]['min'], self.SAFE_RANGES[axis]['max'])
                spinbox.setValue(wp[axis])
                spinbox.valueChanged.connect(lambda v, idx=i, ax=axis: self.update_waypoint(idx, ax, v))
                self.waypoint_table.setCellWidget(i, j, spinbox)

            # Hold time
            hold_spinbox = QDoubleSpinBox()
            hold_spinbox.setRange(0.1, 60.0)
            hold_spinbox.setValue(wp['holdTime'])
            hold_spinbox.setSuffix(" s")
            hold_spinbox.valueChanged.connect(lambda v, idx=i: self.update_waypoint(idx, 'holdTime', v))
            self.waypoint_table.setCellWidget(i, 3, hold_spinbox)

            # Remove button
            remove_btn = QPushButton("Remove")
            remove_btn.setProperty("class", "red")
            remove_btn.clicked.connect(lambda checked, idx=i: self.remove_waypoint(idx))
            self.waypoint_table.setCellWidget(i, 4, remove_btn)

    def update_waypoint(self, index, field, value):
        """Update waypoint value"""
        if index < len(self.waypoints):
            self.waypoints[index][field] = value

    def add_waypoint(self):
        """Add new waypoint"""
        self.waypoints.append({'X': 50.0, 'Y': 50.0, 'Z': 50.0, 'holdTime': 1.0})
        self.update_waypoint_table()

    def remove_waypoint(self, index):
        """Remove waypoint"""
        if len(self.waypoints) > 1 and index < len(self.waypoints):
            self.waypoints.pop(index)
            self.update_waypoint_table()


def main():
    app = QApplication(sys.argv)
    app.setStyle('Fusion')

    window = PIStageGUI()
    window.show()

    sys.exit(app.exec())


if __name__ == '__main__':
    main()