"""
Automated sequence panel with waypoint table.

Source: legacy/PI_Control_GUI/main_gui.py:453-512 (waypoint table UI)
"""

from PySide6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QPushButton,
                                QTableWidget, QHeaderView, QDoubleSpinBox, QLabel,
                                QTableWidgetItem)
from PySide6.QtCore import Signal, Qt
from PySide6.QtGui import QFont

from ...core.models import Axis, Waypoint, Position


class SequencePanel(QWidget):
    """Widget for automated waypoint sequence control.

    Emits signals for start/stop/add/remove operations.
    Controller layer interfaces with MotionService.

    Signals:
        start_requested(waypoints): User clicked start with waypoint list
        stop_requested(): User clicked stop
        add_waypoint_requested(): User clicked add waypoint
    """

    start_requested = Signal(list)  # list[Waypoint]
    stop_requested = Signal()
    add_waypoint_requested = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.waypoints = []
        self._is_running = False
        self._setup_ui()

    def _setup_ui(self):
        """Build UI layout."""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)

        # Title
        title = QLabel("Automated Sequence")
        title.setFont(QFont("Segoe UI", 12, QFont.Bold))
        title.setStyleSheet("color: #e2e8f0;")
        layout.addWidget(title)

        # Control buttons
        btn_layout = QHBoxLayout()

        self.start_btn = QPushButton("▶ Start Sequence")
        self.start_btn.setStyleSheet("""
            QPushButton {
                background: #48bb78;
                color: white;
                border: none;
                padding: 8px 16px;
                border-radius: 4px;
                font-weight: bold;
            }
            QPushButton:hover { background: #38a169; }
            QPushButton:disabled { background: #4a5568; color: #a0aec0; }
        """)
        self.start_btn.clicked.connect(self._on_start_clicked)
        btn_layout.addWidget(self.start_btn)

        self.stop_btn = QPushButton("⏹ Stop")
        self.stop_btn.setStyleSheet("""
            QPushButton {
                background: #f56565;
                color: white;
                border: none;
                padding: 8px 16px;
                border-radius: 4px;
                font-weight: bold;
            }
            QPushButton:hover { background: #e53e3e; }
            QPushButton:disabled { background: #4a5568; color: #a0aec0; }
        """)
        self.stop_btn.setEnabled(False)
        self.stop_btn.clicked.connect(self._on_stop_clicked)
        btn_layout.addWidget(self.stop_btn)

        add_btn = QPushButton("+ Add Waypoint")
        add_btn.setStyleSheet("""
            QPushButton {
                background: rgba(99, 179, 194, 0.3);
                color: #63b3c2;
                border: 1px solid #63b3c2;
                padding: 8px 16px;
                border-radius: 4px;
            }
            QPushButton:hover { background: rgba(99, 179, 194, 0.5); }
        """)
        add_btn.clicked.connect(self._on_add_clicked)
        btn_layout.addWidget(add_btn)

        btn_layout.addStretch()
        layout.addLayout(btn_layout)

        # Status label
        self.status_label = QLabel("Ready")
        self.status_label.setAlignment(Qt.AlignCenter)
        self.status_label.setFont(QFont("Segoe UI", 11, QFont.Bold))
        self.status_label.setStyleSheet("""
            color: #68d391;
            background: rgba(56, 161, 105, 0.2);
            padding: 8px;
            border-radius: 4px;
            margin: 8px 0;
        """)
        layout.addWidget(self.status_label)

        # Waypoints table
        self.waypoint_table = QTableWidget()
        self.waypoint_table.setColumnCount(5)
        self.waypoint_table.setHorizontalHeaderLabels(['X (mm)', 'Y (mm)', 'Z (mm)', 'Hold (s)', 'Action'])
        self.waypoint_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.waypoint_table.setAlternatingRowColors(True)
        self.waypoint_table.setSelectionBehavior(QTableWidget.SelectRows)
        self.waypoint_table.setStyleSheet("""
            QTableWidget {
                background: rgba(0,0,0,0.3);
                color: #e2e8f0;
                border: 1px solid rgba(99, 179, 194, 0.3);
                border-radius: 4px;
                selection-background-color: rgba(99, 179, 194, 0.3);
                selection-color: #e2e8f0;
            }
            QTableWidget::item:selected {
                background: rgba(99, 179, 194, 0.3);
                color: #e2e8f0;
            }
            QHeaderView::section {
                background: rgba(99, 179, 194, 0.2);
                color: #63b3c2;
                padding: 5px;
                border: none;
                font-weight: bold;
            }
        """)
        layout.addWidget(self.waypoint_table)

        # Initialize with default waypoint
        self.waypoints = [
            Waypoint(position=Position(x=50.0, y=50.0, z=50.0), hold_time=1.0)
        ]
        self._update_table()

    def _on_start_clicked(self):
        """Handle start button click."""
        self.start_requested.emit(self.waypoints)

    def _on_stop_clicked(self):
        """Handle stop button click."""
        self.stop_requested.emit()

    def _on_add_clicked(self):
        """Handle add waypoint button click."""
        # Add new waypoint with default values
        self.waypoints.append(Waypoint(position=Position(x=50.0, y=50.0, z=50.0), hold_time=1.0))
        self._update_table()

    def _on_remove_clicked(self, index: int):
        """Handle remove button click for specific waypoint."""
        if 0 <= index < len(self.waypoints):
            self.waypoints.pop(index)
            self._update_table()

    def _update_table(self):
        """Refresh waypoint table from waypoints list."""
        self.waypoint_table.setRowCount(len(self.waypoints))

        for i, wp in enumerate(self.waypoints):
            # X spinbox
            x_spinbox = QDoubleSpinBox()
            x_spinbox.setRange(5.0, 200.0)
            x_spinbox.setValue(wp.position.x)
            x_spinbox.setDecimals(1)
            x_spinbox.valueChanged.connect(lambda val, idx=i: self._update_waypoint(idx, 'x', val))
            self.waypoint_table.setCellWidget(i, 0, x_spinbox)

            # Y spinbox
            y_spinbox = QDoubleSpinBox()
            y_spinbox.setRange(0.0, 200.0)
            y_spinbox.setValue(wp.position.y)
            y_spinbox.setDecimals(1)
            y_spinbox.valueChanged.connect(lambda val, idx=i: self._update_waypoint(idx, 'y', val))
            self.waypoint_table.setCellWidget(i, 1, y_spinbox)

            # Z spinbox
            z_spinbox = QDoubleSpinBox()
            z_spinbox.setRange(15.0, 200.0)
            z_spinbox.setValue(wp.position.z)
            z_spinbox.setDecimals(1)
            z_spinbox.valueChanged.connect(lambda val, idx=i: self._update_waypoint(idx, 'z', val))
            self.waypoint_table.setCellWidget(i, 2, z_spinbox)

            # Hold time spinbox
            hold_spinbox = QDoubleSpinBox()
            hold_spinbox.setRange(0.0, 60.0)
            hold_spinbox.setValue(wp.hold_time)
            hold_spinbox.setDecimals(1)
            hold_spinbox.setSuffix(" s")
            hold_spinbox.valueChanged.connect(lambda val, idx=i: self._update_waypoint(idx, 'hold_time', val))
            self.waypoint_table.setCellWidget(i, 3, hold_spinbox)

            # Remove button
            remove_btn = QPushButton("Remove")
            remove_btn.setStyleSheet("""
                QPushButton {
                    background: #f56565;
                    color: white;
                    border: none;
                    padding: 4px 8px;
                    border-radius: 3px;
                }
                QPushButton:hover { background: #e53e3e; }
            """)
            remove_btn.clicked.connect(lambda _, idx=i: self._on_remove_clicked(idx))
            self.waypoint_table.setCellWidget(i, 4, remove_btn)

    def _update_waypoint(self, index: int, field: str, value: float):
        """Update waypoint field value."""
        if 0 <= index < len(self.waypoints):
            wp = self.waypoints[index]
            # Create new waypoint/position with updated field (dataclasses are frozen)
            if field == 'x':
                new_pos = Position(x=value, y=wp.position.y, z=wp.position.z)
                self.waypoints[index] = Waypoint(position=new_pos, hold_time=wp.hold_time)
            elif field == 'y':
                new_pos = Position(x=wp.position.x, y=value, z=wp.position.z)
                self.waypoints[index] = Waypoint(position=new_pos, hold_time=wp.hold_time)
            elif field == 'z':
                new_pos = Position(x=wp.position.x, y=wp.position.y, z=value)
                self.waypoints[index] = Waypoint(position=new_pos, hold_time=wp.hold_time)
            elif field == 'hold_time':
                self.waypoints[index] = Waypoint(position=wp.position, hold_time=value)

    def set_running(self, running: bool):
        """Update UI for running/stopped state."""
        self._is_running = running
        self.start_btn.setEnabled(not running)
        self.stop_btn.setEnabled(running)

    def set_status(self, status: str, status_type: str = "info"):
        """Update status label.

        Args:
            status: Status message
            status_type: "info", "success", "error"
        """
        self.status_label.setText(status)

        if status_type == "success":
            self.status_label.setStyleSheet("""
                color: #68d391;
                background: rgba(56, 161, 105, 0.2);
                padding: 8px;
                border-radius: 4px;
                margin: 8px 0;
            """)
        elif status_type == "error":
            self.status_label.setStyleSheet("""
                color: #fc8181;
                background: rgba(245, 101, 101, 0.2);
                padding: 8px;
                border-radius: 4px;
                margin: 8px 0;
            """)
        else:  # info
            self.status_label.setStyleSheet("""
                color: #63b3c2;
                background: rgba(99, 179, 194, 0.2);
                padding: 8px;
                border-radius: 4px;
                margin: 8px 0;
            """)

    def set_enabled(self, enabled: bool):
        """Enable/disable all controls."""
        self.start_btn.setEnabled(enabled and not self._is_running)
        self.stop_btn.setEnabled(enabled and self._is_running)
        self.waypoint_table.setEnabled(enabled)
