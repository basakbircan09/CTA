#!/usr/bin/python
# -*- coding: utf-8 -*-
"""
PI Stage Control GUI - Production Version
Integrates actual hardware control from Tmotion2.0.py with user-friendly interface
"""

import sys
import threading
import time
from PySide6.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout,
                               QHBoxLayout, QGridLayout, QLabel, QPushButton,
                               QLineEdit, QRadioButton, QFrame, QTableWidget,
                               QTableWidgetItem, QHeaderView, QSpacerItem,
                               QSizePolicy, QStackedWidget, QDoubleSpinBox,
                               QMessageBox, QTextEdit)
from PySide6.QtCore import Qt, QTimer, Signal, QObject
from PySide6.QtGui import QFont

from hardware_controller import PIHardwareController
from config import (AXIS_TRAVEL_RANGES, MAX_VELOCITY, DEFAULT_VELOCITY,
                   DEFAULT_STEP_SIZE, POSITION_UPDATE_INTERVAL,
                   DEFAULT_WAYPOINTS, DEFAULT_PARK_POSITION)


class WorkerSignals(QObject):
    """Signals for thread communication."""
    finished = Signal()
    error = Signal(str)
    result = Signal(object)
    progress = Signal(str)


class ModernCard(QFrame):
    """Modern styled card widget for GUI sections."""
    def __init__(self, title="", parent=None):
        super().__init__(parent)
        self.setFrameStyle(QFrame.Box)
        self.setStyleSheet("""
            QFrame {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
                    stop:0 rgba(56, 104, 140, 0.3), stop:1 rgba(13, 29, 85, 0.3));
                border: 2px solid rgba(99, 179, 194, 0.3);
                border-radius: 12px;
                padding: 15px;
            }
        """)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 15, 20, 15)

        if title:
            title_label = QLabel(title)
            title_label.setFont(QFont("Segoe UI", 14, QFont.Bold))
            title_label.setStyleSheet("color: #e2e8f0; margin-bottom: 10px; background: transparent; border: none;")
            layout.addWidget(title_label)


class PIStageGUI(QMainWindow):
    """Main GUI application for PI stage control."""

    def __init__(self):
        super().__init__()
        self.setWindowTitle("PI Stage Control System - Production")
        self.setGeometry(100, 100, 1600, 900)

        # Hardware controller
        self.hardware = PIHardwareController()

        # GUI state
        self.is_running = False
        self.waypoints = [wp.copy() for wp in DEFAULT_WAYPOINTS]

        # Set window style
        self.setAutoFillBackground(True)
        self.setStyleSheet("""
            QMainWindow {
                background: qlineargradient(
                    x1:0, y1:0, x2:1, y2:1,
                    stop:0 #0D1D55,
                    stop:1 #38688C
                );
            }
            QLabel {
                color: #FFFFDD;
                background: transparent;
            }
            QPushButton {
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                    stop:0 #63B3C2, stop:1 #38688C);
                color: #FFFFEC;
                border: none;
                padding: 10px 20px;
                border-radius: 8px;
                font-weight: 600;
                font-size: 13px;
            }
            QPushButton:hover {
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                    stop:0 #B1D9D0, stop:1 #63B3C2);
            }
            QPushButton:disabled {
                background: #4a5568;
                color: #999999;
            }
            QPushButton#greenButton {
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                    stop:0 #68d391, stop:1 #38a169);
            }
            QPushButton#redButton {
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                    stop:0 #f56565, stop:1 #e53e3e);
            }
            QLineEdit, QDoubleSpinBox {
                background-color: rgba(99, 179, 194, 0.2);
                color: #FFFFDD;
                border: 2px solid rgba(255, 255, 255, 0.2);
                border-radius: 6px;
                padding: 6px;
                font-size: 13px;
            }
            QLineEdit:focus, QDoubleSpinBox:focus {
                border-color: #B1D9D0;
            }
            QRadioButton {
                color: #FFFFEC;
                font-size: 14px;
                font-weight: 500;
            }
            QRadioButton::indicator:checked {
                background-color: #63B3C2;
                border-color: #63B3C2;
            }
            QTableWidget {
                background-color: rgba(56, 104, 140, 0.6);
                color: #FFFFDD;
                border: none;
                border-radius: 8px;
            }
            QHeaderView::section {
                background-color: #38688C;
                color: #FFFFEC;
                padding: 8px;
                font-weight: 600;
            }
            QTextEdit {
                background-color: rgba(13, 29, 85, 0.5);
                color: #FFFFDD;
                border: 2px solid rgba(99, 179, 194, 0.3);
                border-radius: 6px;
                font-family: 'Consolas', 'Courier New', monospace;
                font-size: 11px;
            }
        """)

        self.setup_ui()
        self.setup_timer()

    def setup_ui(self):
        """Setup the user interface."""
        central_widget = QWidget()
        self.setCentralWidget(central_widget)

        main_layout = QHBoxLayout(central_widget)
        main_layout.setSpacing(20)
        main_layout.setContentsMargins(20, 20, 20, 20)

        # Left column
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

        # Connection panel
        self.setup_connection_panel(left_col)

        # Position display
        self.setup_position_display(left_col)

        # Velocity panel
        self.setup_velocity_panel(left_col)

        # Console log
        self.setup_console_log(left_col)

        # Right column
        right_col = QVBoxLayout()
        right_col.setSpacing(20)

        # Mode switcher
        self.setup_mode_switcher(right_col)

        # Control stack
        self.setup_control_stack(right_col)

        # Add columns to main layout
        main_layout.addLayout(left_col, 1)
        main_layout.addLayout(right_col, 2)

    def setup_connection_panel(self, layout):
        """Connection and initialization panel."""
        conn_card = ModernCard("Connection & Initialization")
        conn_layout = conn_card.layout()

        # Status indicator
        status_container = QWidget()
        status_layout = QHBoxLayout(status_container)
        status_layout.setContentsMargins(0, 0, 0, 10)

        status_layout.addWidget(QLabel("Status:"))
        self.status_indicator = QLabel("● Disconnected")
        self.status_indicator.setStyleSheet("color: #f56565; font-weight: bold; font-size: 14px;")
        status_layout.addWidget(self.status_indicator)
        status_layout.addStretch()

        conn_layout.addWidget(status_container)

        # Buttons
        btn_container = QWidget()
        btn_layout = QHBoxLayout(btn_container)
        btn_layout.setSpacing(10)

        self.connect_btn = QPushButton("Connect Controllers")
        self.connect_btn.setObjectName("greenButton")
        self.connect_btn.clicked.connect(self.connect_hardware)
        btn_layout.addWidget(self.connect_btn)

        self.init_btn = QPushButton("Initialize & Reference")
        self.init_btn.setEnabled(False)
        self.init_btn.clicked.connect(self.initialize_hardware)
        btn_layout.addWidget(self.init_btn)

        self.disconnect_btn = QPushButton("Disconnect")
        self.disconnect_btn.setObjectName("redButton")
        self.disconnect_btn.setEnabled(False)
        self.disconnect_btn.clicked.connect(self.disconnect_hardware)
        btn_layout.addWidget(self.disconnect_btn)

        conn_layout.addWidget(btn_container)
        layout.addWidget(conn_card)

    def setup_position_display(self, layout):
        """Real-time position display."""
        pos_card = ModernCard("Current Position (Live)")
        pos_layout = pos_card.layout()

        grid_widget = QWidget()
        grid_layout = QGridLayout(grid_widget)
        grid_layout.setSpacing(30)

        self.pos_labels = {}
        for i, axis in enumerate(['X', 'Y', 'Z']):
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

            axis_label = QLabel(f"{axis}-Axis")
            axis_label.setAlignment(Qt.AlignCenter)
            axis_label.setFont(QFont("Segoe UI", 16, QFont.Bold))
            axis_label.setStyleSheet("color: #4299e1; margin-bottom: 5px;")
            axis_layout.addWidget(axis_label)

            self.pos_labels[axis] = QLabel("0.000")
            self.pos_labels[axis].setAlignment(Qt.AlignCenter)
            self.pos_labels[axis].setFont(QFont("Segoe UI", 28, QFont.Bold))
            self.pos_labels[axis].setStyleSheet("""
                color: #00d4aa;
                margin: 10px;
                text-shadow: 0 0 15px rgba(0, 212, 170, 0.6);
            """)
            axis_layout.addWidget(self.pos_labels[axis])

            units = QLabel("mm")
            units.setAlignment(Qt.AlignCenter)
            units.setStyleSheet("color: #a0aec0; font-size: 14px; margin-bottom: 5px;")
            axis_layout.addWidget(units)

            range_text = f"Range: {AXIS_TRAVEL_RANGES[axis]['min']}-{AXIS_TRAVEL_RANGES[axis]['max']}"
            range_label = QLabel(range_text)
            range_label.setAlignment(Qt.AlignCenter)
            range_label.setStyleSheet("color: #718096; font-size: 11px;")
            axis_layout.addWidget(range_label)

            grid_layout.addWidget(axis_frame, 0, i)

        pos_layout.addWidget(grid_widget)
        layout.addWidget(pos_card)

    def setup_velocity_panel(self, layout):
        """Velocity control panel."""
        vel_card = ModernCard("Velocity Settings")
        vel_layout = vel_card.layout()

        grid_widget = QWidget()
        grid_layout = QGridLayout(grid_widget)

        self.vel_spinboxes = {}
        for i, axis in enumerate(['X', 'Y', 'Z']):
            label = QLabel(f"{axis}-Axis")
            label.setAlignment(Qt.AlignCenter)
            label.setFont(QFont("Segoe UI", 12, QFont.Bold))
            grid_layout.addWidget(label, 0, i)

            self.vel_spinboxes[axis] = QDoubleSpinBox()
            self.vel_spinboxes[axis].setRange(0.1, MAX_VELOCITY)
            self.vel_spinboxes[axis].setValue(DEFAULT_VELOCITY)
            self.vel_spinboxes[axis].setSuffix(" mm/s")
            self.vel_spinboxes[axis].setDecimals(1)
            self.vel_spinboxes[axis].valueChanged.connect(lambda v, ax=axis: self.set_velocity(ax, v))
            grid_layout.addWidget(self.vel_spinboxes[axis], 1, i)

            max_label = QLabel(f"Max: {MAX_VELOCITY} mm/s")
            max_label.setAlignment(Qt.AlignCenter)
            max_label.setStyleSheet("color: #a0aec0; font-size: 10px;")
            grid_layout.addWidget(max_label, 2, i)

        vel_layout.addWidget(grid_widget)
        layout.addWidget(vel_card)

    def setup_console_log(self, layout):
        """Console log for system messages."""
        console_card = ModernCard("System Log")
        console_layout = console_card.layout()

        self.console = QTextEdit()
        self.console.setReadOnly(True)
        self.console.setMaximumHeight(150)
        console_layout.addWidget(self.console)

        layout.addWidget(console_card)

    def setup_mode_switcher(self, layout):
        """Mode selection switcher."""
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

    def setup_control_stack(self, layout):
        """Stacked widget for manual/automated controls."""
        self.control_stack = QStackedWidget()

        self.setup_manual_page()
        self.setup_automated_page()

        layout.addWidget(self.control_stack)

    def setup_manual_page(self):
        """Manual control page with MVR commands."""
        manual_page = QWidget()
        page_layout = QVBoxLayout(manual_page)

        manual_card = ModernCard("Manual Control (MVR)")
        manual_layout = manual_card.layout()

        # Step size control
        step_container = QWidget()
        step_layout = QHBoxLayout(step_container)

        step_layout.addWidget(QLabel("Step Size:"))

        self.step_spinbox = QDoubleSpinBox()
        self.step_spinbox.setRange(0.1, 50.0)
        self.step_spinbox.setValue(DEFAULT_STEP_SIZE)
        self.step_spinbox.setSuffix(" mm")
        self.step_spinbox.setDecimals(1)
        step_layout.addWidget(self.step_spinbox)

        step_layout.addStretch()
        manual_layout.addWidget(step_container)

        # Axis controls
        controls_widget = QWidget()
        controls_layout = QGridLayout(controls_widget)
        controls_layout.setSpacing(25)

        for i, axis in enumerate(['X', 'Y', 'Z']):
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

            axis_title = QLabel(f"{axis}-Axis")
            axis_title.setAlignment(Qt.AlignCenter)
            axis_title.setFont(QFont("Segoe UI", 14, QFont.Bold))
            axis_title.setStyleSheet("color: #68d391; margin-bottom: 10px;")
            axis_layout.addWidget(axis_title)

            pos_btn = QPushButton(f"+ Move")
            pos_btn.setObjectName("greenButton")
            pos_btn.clicked.connect(lambda checked, ax=axis: self.move_relative(ax, self.step_spinbox.value()))
            axis_layout.addWidget(pos_btn)

            axis_layout.addSpacing(10)

            neg_btn = QPushButton(f"- Move")
            neg_btn.setObjectName("redButton")
            neg_btn.clicked.connect(lambda checked, ax=axis: self.move_relative(ax, -self.step_spinbox.value()))
            axis_layout.addWidget(neg_btn)

            controls_layout.addWidget(axis_container, 0, i)

        manual_layout.addWidget(controls_widget)

        # Park button
        park_btn = QPushButton("Park All Axes")
        park_btn.setObjectName("redButton")
        park_btn.clicked.connect(self.park_axes)
        manual_layout.addWidget(park_btn)

        page_layout.addWidget(manual_card)
        self.control_stack.addWidget(manual_page)

    def setup_automated_page(self):
        """Automated sequence page with waypoint table."""
        auto_page = QWidget()
        page_layout = QVBoxLayout(auto_page)

        auto_card = ModernCard("Automated Sequence (MOV)")
        auto_layout = auto_card.layout()

        # Control buttons
        btn_container = QWidget()
        btn_layout = QHBoxLayout(btn_container)

        self.start_btn = QPushButton("▶ Start Sequence")
        self.start_btn.setObjectName("greenButton")
        self.start_btn.clicked.connect(self.start_automated_sequence)
        btn_layout.addWidget(self.start_btn)

        self.stop_btn = QPushButton("⏹ Stop Motion")
        self.stop_btn.setObjectName("redButton")
        self.stop_btn.setEnabled(False)
        self.stop_btn.clicked.connect(self.stop_motion)
        btn_layout.addWidget(self.stop_btn)

        add_btn = QPushButton("+ Add Waypoint")
        add_btn.clicked.connect(self.add_waypoint)
        btn_layout.addWidget(add_btn)

        park_btn = QPushButton("Park All Axes")
        park_btn.setObjectName("redButton")
        park_btn.clicked.connect(self.park_axes)
        btn_layout.addWidget(park_btn)

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

        # Waypoints table
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
        """Setup timer for position updates."""
        self.timer = QTimer()
        self.timer.timeout.connect(self.update_position_display)
        self.timer.start(POSITION_UPDATE_INTERVAL)

    def log_message(self, message):
        """Add message to console log."""
        self.console.append(message)

    def connect_hardware(self):
        """Connect to hardware controllers."""
        self.connect_btn.setEnabled(False)
        self.log_message("Connecting to controllers...")

        def connection_thread():
            success, message = self.hardware.connect_controllers()
            return success, message

        # Run in thread
        thread = threading.Thread(target=lambda: self.handle_connection_result(connection_thread()))
        thread.start()

    def handle_connection_result(self, result):
        """Handle connection result."""
        success, message = result

        if success:
            self.status_indicator.setText("● Connected")
            self.status_indicator.setStyleSheet("color: #68d391; font-weight: bold; font-size: 14px;")
            self.log_message(message)
            self.init_btn.setEnabled(True)
            self.disconnect_btn.setEnabled(True)
        else:
            self.status_indicator.setText("● Connection Failed")
            self.status_indicator.setStyleSheet("color: #f56565; font-weight: bold; font-size: 14px;")
            self.log_message(f"ERROR: {message}")
            self.connect_btn.setEnabled(True)
            QMessageBox.critical(self, "Connection Error", message)

    def initialize_hardware(self):
        """Initialize and reference hardware."""
        reply = QMessageBox.question(self, 'Confirm Initialization',
                                     'This will reference all stages. The stages will move!\n\n'
                                     'Ensure the workspace is clear. Continue?',
                                     QMessageBox.Yes | QMessageBox.No, QMessageBox.No)

        if reply != QMessageBox.Yes:
            return

        self.init_btn.setEnabled(False)
        self.log_message("Initializing and referencing stages...")

        def init_thread():
            success, message = self.hardware.initialize_and_reference()
            return success, message

        thread = threading.Thread(target=lambda: self.handle_init_result(init_thread()))
        thread.start()

    def handle_init_result(self, result):
        """Handle initialization result."""
        success, message = result

        if success:
            self.status_indicator.setText("● Ready")
            self.status_indicator.setStyleSheet("color: #00d4aa; font-weight: bold; font-size: 14px;")
            self.log_message(message)
            QMessageBox.information(self, "Success", "System initialized and ready for motion!")
        else:
            self.status_indicator.setText("● Initialization Failed")
            self.status_indicator.setStyleSheet("color: #f56565; font-weight: bold; font-size: 14px;")
            self.log_message(f"ERROR: {message}")
            self.init_btn.setEnabled(True)
            QMessageBox.critical(self, "Initialization Error", message)

    def disconnect_hardware(self):
        """Disconnect from hardware."""
        self.hardware.disconnect_controllers()
        self.status_indicator.setText("● Disconnected")
        self.status_indicator.setStyleSheet("color: #f56565; font-weight: bold; font-size: 14px;")
        self.log_message("Disconnected from controllers")

        self.connect_btn.setEnabled(True)
        self.init_btn.setEnabled(False)
        self.disconnect_btn.setEnabled(False)

    def set_velocity(self, axis, velocity):
        """Set velocity for axis."""
        success, message = self.hardware.set_velocity(axis, velocity)
        if success:
            self.log_message(f"Velocity {axis}: {velocity:.1f} mm/s")
        else:
            self.log_message(f"ERROR: {message}")

    def move_relative(self, axis, distance):
        """Move axis by relative distance."""
        success, message = self.hardware.move_relative(axis, distance)
        if success:
            self.log_message(message)
        else:
            self.log_message(f"ERROR: {message}")
            QMessageBox.warning(self, "Move Error", message)

    def park_axes(self):
        """Park all axes to default position."""
        reply = QMessageBox.question(self, 'Confirm Park',
                                     f'Move all axes to park position ({DEFAULT_PARK_POSITION} mm)?',
                                     QMessageBox.Yes | QMessageBox.No, QMessageBox.No)

        if reply != QMessageBox.Yes:
            return

        self.log_message("Parking axes...")

        def park_thread():
            success, message = self.hardware.reset_to_park(DEFAULT_PARK_POSITION)
            return success, message

        thread = threading.Thread(target=lambda: self.handle_park_result(park_thread()))
        thread.start()

    def handle_park_result(self, result):
        """Handle park result."""
        success, message = result
        if success:
            self.log_message(message)
        else:
            self.log_message(f"ERROR: {message}")
            QMessageBox.warning(self, "Park Error", message)

    def start_automated_sequence(self):
        """Start automated waypoint sequence."""
        if not self.waypoints:
            QMessageBox.warning(self, "No Waypoints", "Please add waypoints before starting sequence.")
            return

        reply = QMessageBox.question(self, 'Confirm Sequence',
                                     f'Start automated sequence with {len(self.waypoints)} waypoints?',
                                     QMessageBox.Yes | QMessageBox.No, QMessageBox.No)

        if reply != QMessageBox.Yes:
            return

        self.is_running = True
        self.start_btn.setEnabled(False)
        self.stop_btn.setEnabled(True)
        self.log_message("Starting automated sequence...")

        threading.Thread(target=self.run_sequence, daemon=True).start()

    def run_sequence(self):
        """Execute waypoint sequence."""
        for i, waypoint in enumerate(self.waypoints):
            if not self.is_running:
                break

            self.status_label.setText(f"Waypoint {i + 1}/{len(self.waypoints)}")
            self.log_message(f"Moving to waypoint {i + 1}: X={waypoint['X']}, Y={waypoint['Y']}, Z={waypoint['Z']}")

            # Command all axes to move
            for axis in ['X', 'Y', 'Z']:
                if axis in waypoint:
                    self.hardware.move_absolute(axis, waypoint[axis])

            # Wait for all axes to reach target
            for axis in ['X', 'Y', 'Z']:
                self.hardware.wait_for_target(axis)

            self.log_message(f"Waypoint {i + 1} reached. Holding for {waypoint['holdTime']}s...")
            time.sleep(waypoint['holdTime'])

        self.sequence_complete()

    def stop_motion(self):
        """Stop motion sequence."""
        self.is_running = False
        self.hardware.stop_all()
        self.log_message("Motion stopped by user")
        self.sequence_complete()

    def sequence_complete(self):
        """Reset after sequence completion."""
        self.is_running = False
        self.start_btn.setEnabled(True)
        self.stop_btn.setEnabled(False)
        self.status_label.setText("Sequence Complete")
        self.log_message("Sequence complete")

    def update_position_display(self):
        """Update position labels from hardware."""
        if self.hardware.initialized:
            positions = self.hardware.get_all_positions()
            for axis in ['X', 'Y', 'Z']:
                self.pos_labels[axis].setText(f"{positions[axis]:.3f}")

    def mode_changed(self):
        """Handle mode selection."""
        if self.manual_radio.isChecked():
            self.control_stack.setCurrentIndex(0)
        else:
            self.control_stack.setCurrentIndex(1)

    def update_waypoint_table(self):
        """Update waypoints table."""
        self.waypoint_table.setRowCount(len(self.waypoints))

        for i, wp in enumerate(self.waypoints):
            for j, axis in enumerate(['X', 'Y', 'Z']):
                spinbox = QDoubleSpinBox()
                spinbox.setRange(AXIS_TRAVEL_RANGES[axis]['min'], AXIS_TRAVEL_RANGES[axis]['max'])
                spinbox.setValue(wp[axis])
                spinbox.valueChanged.connect(lambda v, idx=i, ax=axis: self.update_waypoint(idx, ax, v))
                self.waypoint_table.setCellWidget(i, j, spinbox)

            hold_spinbox = QDoubleSpinBox()
            hold_spinbox.setRange(0.1, 60.0)
            hold_spinbox.setValue(wp['holdTime'])
            hold_spinbox.setSuffix(" s")
            hold_spinbox.valueChanged.connect(lambda v, idx=i: self.update_waypoint(idx, 'holdTime', v))
            self.waypoint_table.setCellWidget(i, 3, hold_spinbox)

            remove_btn = QPushButton("Remove")
            remove_btn.setObjectName("redButton")
            remove_btn.clicked.connect(lambda checked, idx=i: self.remove_waypoint(idx))
            self.waypoint_table.setCellWidget(i, 4, remove_btn)

    def update_waypoint(self, index, field, value):
        """Update waypoint value."""
        if index < len(self.waypoints):
            self.waypoints[index][field] = value

    def add_waypoint(self):
        """Add new waypoint."""
        self.waypoints.append({'X': 50.0, 'Y': 50.0, 'Z': 50.0, 'holdTime': 1.0})
        self.update_waypoint_table()

    def remove_waypoint(self, index):
        """Remove waypoint."""
        if len(self.waypoints) > 1 and index < len(self.waypoints):
            self.waypoints.pop(index)
            self.update_waypoint_table()

    def closeEvent(self, event):
        """Handle window close."""
        if self.hardware.connected:
            reply = QMessageBox.question(self, 'Confirm Exit',
                                        'Disconnect from hardware and exit?',
                                        QMessageBox.Yes | QMessageBox.No, QMessageBox.No)

            if reply == QMessageBox.Yes:
                self.hardware.disconnect_controllers()
                event.accept()
            else:
                event.ignore()
        else:
            event.accept()


def main():
    """Main application entry point."""
    app = QApplication(sys.argv)
    app.setStyle('Fusion')

    window = PIStageGUI()
    window.show()

    sys.exit(app.exec())


if __name__ == '__main__':
    main()
