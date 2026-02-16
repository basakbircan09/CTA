#!/usr/bin/python
# -*- coding: utf-8 -*-
"""
PI Stage Control GUI - Production Version (Fixed)
Fixes: 1) Scalability/scroll support 2) Threading for dialogs 3) Classic dark theme
"""

import sys
import threading
import time
from PySide6.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout,
                               QHBoxLayout, QGridLayout, QLabel, QPushButton,
                               QRadioButton, QFrame, QTableWidget,
                               QHeaderView, QStackedWidget, QDoubleSpinBox,
                               QMessageBox, QTextEdit, QScrollArea)
from PySide6.QtCore import Qt, QTimer, Signal, QObject
from PySide6.QtGui import QFont, QPalette, QColor

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


class SimpleCard(QFrame):
    """Simple card widget with classic dark theme."""
    def __init__(self, title="", parent=None):
        super().__init__(parent)
        self.setFrameStyle(QFrame.Box)
        self.setStyleSheet("""
            QFrame {
                background-color: #3a3a3a;
                border: 1px solid #555555;
                border-radius: 5px;
                padding: 10px;
            }
        """)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(15, 10, 15, 10)

        if title:
            title_label = QLabel(title)
            title_label.setFont(QFont("Arial", 11, QFont.Bold))
            title_label.setStyleSheet("color: #ffffff; background: transparent; border: none;")
            layout.addWidget(title_label)


class PIStageGUI(QMainWindow):
    """Main GUI application for PI stage control."""

    # Signals for thread-safe GUI updates
    connection_result = Signal(bool, str)
    init_result = Signal(bool, str)
    park_result = Signal(bool, str)

    def __init__(self):
        super().__init__()
        self.setWindowTitle("PI Stage Control System")
        self.setGeometry(100, 100, 1400, 750)
        self.setMinimumSize(1200, 600)

        # Hardware controller
        self.hardware = PIHardwareController()

        # GUI state
        self.is_running = False
        self.waypoints = [wp.copy() for wp in DEFAULT_WAYPOINTS]

        # Connect signals
        self.connection_result.connect(self.handle_connection_result)
        self.init_result.connect(self.handle_init_result)
        self.park_result.connect(self.handle_park_result)

        # Apply classic dark theme
        self.setup_classic_theme()
        self.setup_ui()
        self.setup_timer()

    def setup_classic_theme(self):
        """Setup classic dark gray theme with good contrast."""
        self.setStyleSheet("""
            QMainWindow {
                background-color: #2b2b2b;
            }
            QLabel {
                color: #ffffff;
                background: transparent;
            }
            QPushButton {
                background-color: #4a4a4a;
                color: #ffffff;
                border: 1px solid #666666;
                padding: 8px 16px;
                border-radius: 3px;
                font-size: 12px;
            }
            QPushButton:hover {
                background-color: #5a5a5a;
                border: 1px solid #888888;
            }
            QPushButton:pressed {
                background-color: #3a3a3a;
            }
            QPushButton:disabled {
                background-color: #333333;
                color: #666666;
            }
            QPushButton#greenButton {
                background-color: #2d5a2d;
                border: 1px solid #3d7a3d;
            }
            QPushButton#greenButton:hover {
                background-color: #3d7a3d;
            }
            QPushButton#redButton {
                background-color: #5a2d2d;
                border: 1px solid #7a3d3d;
            }
            QPushButton#redButton:hover {
                background-color: #7a3d3d;
            }
            QLineEdit, QDoubleSpinBox {
                background-color: #3a3a3a;
                color: #ffffff;
                border: 1px solid #555555;
                border-radius: 3px;
                padding: 5px;
                font-size: 12px;
            }
            QLineEdit:focus, QDoubleSpinBox:focus {
                border: 1px solid #888888;
            }
            QRadioButton {
                color: #ffffff;
                font-size: 13px;
            }
            QRadioButton::indicator:checked {
                background-color: #4a90d9;
                border: 2px solid #4a90d9;
            }
            QTableWidget {
                background-color: #3a3a3a;
                color: #ffffff;
                border: 1px solid #555555;
                gridline-color: #555555;
            }
            QHeaderView::section {
                background-color: #4a4a4a;
                color: #ffffff;
                padding: 6px;
                border: 1px solid #555555;
                font-weight: bold;
            }
            QTextEdit {
                background-color: #1a1a1a;
                color: #00ff00;
                border: 1px solid #555555;
                font-family: 'Consolas', 'Courier New', monospace;
                font-size: 10px;
            }
            QScrollArea {
                border: none;
                background-color: #2b2b2b;
            }
        """)

    def setup_ui(self):
        """Setup the user interface with scroll support."""
        central_widget = QWidget()
        self.setCentralWidget(central_widget)

        # Main scroll area for full scalability
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        scroll.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)

        scroll_content = QWidget()
        scroll.setWidget(scroll_content)

        main_container_layout = QVBoxLayout(central_widget)
        main_container_layout.setContentsMargins(0, 0, 0, 0)
        main_container_layout.addWidget(scroll)

        main_layout = QHBoxLayout(scroll_content)
        main_layout.setSpacing(15)
        main_layout.setContentsMargins(15, 15, 15, 15)

        # Left column
        left_col = QVBoxLayout()
        left_col.setSpacing(15)

        # Title
        title = QLabel("PI Stage Control System")
        title.setAlignment(Qt.AlignCenter)
        title.setFont(QFont("Arial", 20, QFont.Bold))
        title.setStyleSheet("color: #4a90d9; margin: 5px;")
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
        right_col.setSpacing(15)

        # Mode switcher
        self.setup_mode_switcher(right_col)

        # Control stack
        self.setup_control_stack(right_col)

        # Add columns to main layout
        main_layout.addLayout(left_col, 1)
        main_layout.addLayout(right_col, 2)

    def setup_connection_panel(self, layout):
        """Connection and initialization panel."""
        conn_card = SimpleCard("Connection & Initialization")
        conn_layout = conn_card.layout()

        # Status indicator
        status_container = QWidget()
        status_layout = QHBoxLayout(status_container)
        status_layout.setContentsMargins(0, 5, 0, 5)

        status_layout.addWidget(QLabel("Status:"))
        self.status_indicator = QLabel("● Disconnected")
        self.status_indicator.setStyleSheet("color: #ff5555; font-weight: bold;")
        status_layout.addWidget(self.status_indicator)
        status_layout.addStretch()

        conn_layout.addWidget(status_container)

        # Buttons
        btn_container = QWidget()
        btn_layout = QHBoxLayout(btn_container)
        btn_layout.setSpacing(10)

        self.connect_btn = QPushButton("Connect")
        self.connect_btn.setObjectName("greenButton")
        self.connect_btn.clicked.connect(self.connect_hardware)
        btn_layout.addWidget(self.connect_btn)

        self.init_btn = QPushButton("Initialize")
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
        pos_card = SimpleCard("Current Position")
        pos_layout = pos_card.layout()

        grid_widget = QWidget()
        grid_layout = QGridLayout(grid_widget)
        grid_layout.setSpacing(20)

        self.pos_labels = {}
        for i, axis in enumerate(['X', 'Y', 'Z']):
            axis_frame = QFrame()
            axis_frame.setStyleSheet("""
                QFrame {
                    background-color: #333333;
                    border: 1px solid #555555;
                    border-radius: 3px;
                    padding: 10px;
                }
            """)
            axis_layout = QVBoxLayout(axis_frame)

            axis_label = QLabel(f"{axis}-Axis")
            axis_label.setAlignment(Qt.AlignCenter)
            axis_label.setFont(QFont("Arial", 12, QFont.Bold))
            axis_label.setStyleSheet("color: #4a90d9;")
            axis_layout.addWidget(axis_label)

            self.pos_labels[axis] = QLabel("0.000")
            self.pos_labels[axis].setAlignment(Qt.AlignCenter)
            self.pos_labels[axis].setFont(QFont("Arial", 22, QFont.Bold))
            self.pos_labels[axis].setStyleSheet("color: #00ff88;")
            axis_layout.addWidget(self.pos_labels[axis])

            units = QLabel("mm")
            units.setAlignment(Qt.AlignCenter)
            units.setStyleSheet("color: #aaaaaa; font-size: 11px;")
            axis_layout.addWidget(units)

            range_text = f"[{AXIS_TRAVEL_RANGES[axis]['min']}-{AXIS_TRAVEL_RANGES[axis]['max']}]"
            range_label = QLabel(range_text)
            range_label.setAlignment(Qt.AlignCenter)
            range_label.setStyleSheet("color: #888888; font-size: 9px;")
            axis_layout.addWidget(range_label)

            grid_layout.addWidget(axis_frame, 0, i)

        pos_layout.addWidget(grid_widget)
        layout.addWidget(pos_card)

    def setup_velocity_panel(self, layout):
        """Velocity control panel."""
        vel_card = SimpleCard("Velocity Settings")
        vel_layout = vel_card.layout()

        grid_widget = QWidget()
        grid_layout = QGridLayout(grid_widget)

        self.vel_spinboxes = {}
        for i, axis in enumerate(['X', 'Y', 'Z']):
            label = QLabel(f"{axis}-Axis")
            label.setAlignment(Qt.AlignCenter)
            label.setFont(QFont("Arial", 10, QFont.Bold))
            grid_layout.addWidget(label, 0, i)

            self.vel_spinboxes[axis] = QDoubleSpinBox()
            self.vel_spinboxes[axis].setRange(0.1, MAX_VELOCITY)
            self.vel_spinboxes[axis].setValue(DEFAULT_VELOCITY)
            self.vel_spinboxes[axis].setSuffix(" mm/s")
            self.vel_spinboxes[axis].setDecimals(1)
            self.vel_spinboxes[axis].valueChanged.connect(lambda v, ax=axis: self.set_velocity(ax, v))
            grid_layout.addWidget(self.vel_spinboxes[axis], 1, i)

            max_label = QLabel(f"Max: {MAX_VELOCITY}")
            max_label.setAlignment(Qt.AlignCenter)
            max_label.setStyleSheet("color: #888888; font-size: 9px;")
            grid_layout.addWidget(max_label, 2, i)

        vel_layout.addWidget(grid_widget)
        layout.addWidget(vel_card)

    def setup_console_log(self, layout):
        """Console log for system messages."""
        console_card = SimpleCard("System Log")
        console_layout = console_card.layout()

        self.console = QTextEdit()
        self.console.setReadOnly(True)
        self.console.setMaximumHeight(120)
        self.console.setMinimumHeight(80)
        console_layout.addWidget(self.console)

        layout.addWidget(console_card)

    def setup_mode_switcher(self, layout):
        """Mode selection switcher."""
        mode_card = SimpleCard("Control Mode")
        mode_layout = mode_card.layout()

        switch_layout = QHBoxLayout()
        switch_layout.addStretch()

        self.manual_radio = QRadioButton("Manual Control")
        self.manual_radio.setChecked(True)
        self.manual_radio.toggled.connect(self.mode_changed)
        switch_layout.addWidget(self.manual_radio)

        switch_layout.addSpacing(40)

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

        manual_card = SimpleCard("Manual Control (Relative Move)")
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
        controls_layout.setSpacing(20)

        for i, axis in enumerate(['X', 'Y', 'Z']):
            axis_container = QFrame()
            axis_container.setStyleSheet("""
                QFrame {
                    background-color: #333333;
                    border: 1px solid #555555;
                    border-radius: 3px;
                    padding: 15px;
                }
            """)
            axis_layout = QVBoxLayout(axis_container)

            axis_title = QLabel(f"{axis}-Axis")
            axis_title.setAlignment(Qt.AlignCenter)
            axis_title.setFont(QFont("Arial", 11, QFont.Bold))
            axis_title.setStyleSheet("color: #4a90d9;")
            axis_layout.addWidget(axis_title)

            pos_btn = QPushButton(f"+ {axis}")
            pos_btn.setObjectName("greenButton")
            pos_btn.clicked.connect(lambda checked, ax=axis: self.move_relative(ax, self.step_spinbox.value()))
            axis_layout.addWidget(pos_btn)

            axis_layout.addSpacing(5)

            neg_btn = QPushButton(f"- {axis}")
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

        auto_card = SimpleCard("Automated Sequence")
        auto_layout = auto_card.layout()

        # Control buttons
        btn_container = QWidget()
        btn_layout = QHBoxLayout(btn_container)

        self.start_btn = QPushButton("▶ Start")
        self.start_btn.setObjectName("greenButton")
        self.start_btn.clicked.connect(self.start_automated_sequence)
        btn_layout.addWidget(self.start_btn)

        self.stop_btn = QPushButton("⏹ Stop")
        self.stop_btn.setObjectName("redButton")
        self.stop_btn.setEnabled(False)
        self.stop_btn.clicked.connect(self.stop_motion)
        btn_layout.addWidget(self.stop_btn)

        add_btn = QPushButton("+ Waypoint")
        add_btn.clicked.connect(self.add_waypoint)
        btn_layout.addWidget(add_btn)

        park_btn = QPushButton("Park")
        park_btn.setObjectName("redButton")
        park_btn.clicked.connect(self.park_axes)
        btn_layout.addWidget(park_btn)

        btn_layout.addStretch()
        auto_layout.addWidget(btn_container)

        # Status indicator
        self.status_label = QLabel("Ready")
        self.status_label.setAlignment(Qt.AlignCenter)
        self.status_label.setFont(QFont("Arial", 12, QFont.Bold))
        self.status_label.setStyleSheet("""
            color: #00ff88;
            background-color: #333333;
            padding: 8px;
            border-radius: 3px;
            border: 1px solid #555555;
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
            self.connection_result.emit(success, message)

        thread = threading.Thread(target=connection_thread, daemon=True)
        thread.start()

    def handle_connection_result(self, success, message):
        """Handle connection result (thread-safe)."""
        if success:
            self.status_indicator.setText("● Connected")
            self.status_indicator.setStyleSheet("color: #00ff88; font-weight: bold;")
            self.log_message(message)
            self.init_btn.setEnabled(True)
            self.disconnect_btn.setEnabled(True)
        else:
            self.status_indicator.setText("● Failed")
            self.status_indicator.setStyleSheet("color: #ff5555; font-weight: bold;")
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
            self.init_result.emit(success, message)

        thread = threading.Thread(target=init_thread, daemon=True)
        thread.start()

    def handle_init_result(self, success, message):
        """Handle initialization result (thread-safe)."""
        if success:
            self.status_indicator.setText("● Ready")
            self.status_indicator.setStyleSheet("color: #00ffff; font-weight: bold;")
            self.log_message(message)
            QMessageBox.information(self, "Success", "System initialized and ready!")
        else:
            self.status_indicator.setText("● Init Failed")
            self.status_indicator.setStyleSheet("color: #ff5555; font-weight: bold;")
            self.log_message(f"ERROR: {message}")
            self.init_btn.setEnabled(True)
            QMessageBox.critical(self, "Initialization Error", message)

    def disconnect_hardware(self):
        """Disconnect from hardware."""
        self.hardware.disconnect_controllers()
        self.status_indicator.setText("● Disconnected")
        self.status_indicator.setStyleSheet("color: #ff5555; font-weight: bold;")
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
            self.park_result.emit(success, message)

        thread = threading.Thread(target=park_thread, daemon=True)
        thread.start()

    def handle_park_result(self, success, message):
        """Handle park result (thread-safe)."""
        if success:
            self.log_message(message)
        else:
            self.log_message(f"ERROR: {message}")
            QMessageBox.warning(self, "Park Error", message)

    def start_automated_sequence(self):
        """Start automated waypoint sequence."""
        if not self.waypoints:
            QMessageBox.warning(self, "No Waypoints", "Please add waypoints before starting.")
            return

        reply = QMessageBox.question(self, 'Confirm Sequence',
                                     f'Start sequence with {len(self.waypoints)} waypoints?',
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

            self.log_message(f"Waypoint {i + 1} reached. Holding {waypoint['holdTime']}s...")
            time.sleep(waypoint['holdTime'])

        self.sequence_complete()

    def stop_motion(self):
        """Stop motion sequence."""
        self.is_running = False
        self.hardware.stop_all()
        self.log_message("Motion stopped")
        self.sequence_complete()

    def sequence_complete(self):
        """Reset after sequence completion."""
        self.is_running = False
        self.start_btn.setEnabled(True)
        self.stop_btn.setEnabled(False)
        self.status_label.setText("Complete")
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
