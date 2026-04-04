from PySide6.QtWidgets import (
    QGroupBox, QVBoxLayout, QHBoxLayout, QGridLayout,
    QLabel, QDoubleSpinBox, QPushButton,
)
from PySide6.QtCore import Signal

from device_drivers.PI_Control_System.core.models import Axis, Position


class StageControlPanel(QGroupBox):
    """Stage position display, jog buttons, and go-to controls."""

    jog_requested = Signal(object, float)   # (Axis, signed_step_mm)
    goto_requested = Signal(object)         # Position target
    refresh_requested = Signal()

    def __init__(self, parent=None):
        super().__init__("Stage Control", parent)
        self.setStyleSheet("QGroupBox { font-weight: bold; }")

        layout = QVBoxLayout(self)
        layout.setSpacing(10)

        # Current position display
        self.pos_label = QLabel("Position:  X = ?.??    Y = ?.??    Z = ?.??")
        self.pos_label.setStyleSheet("""
            QLabel {
                font-family: monospace;
                font-size: 12px;
                padding: 8px;
                background-color: #1a1a1a;
                border-radius: 4px;
            }
        """)
        layout.addWidget(self.pos_label)

        # Step size + Refresh row
        step_layout = QHBoxLayout()
        step_layout.addWidget(QLabel("Step (mm):"))
        self.spin_step = QDoubleSpinBox()
        self.spin_step.setRange(0.1, 50.0)
        self.spin_step.setValue(5.0)
        self.spin_step.setSingleStep(1.0)
        self.spin_step.setDecimals(1)
        self.spin_step.setMaximumWidth(80)
        step_layout.addWidget(self.spin_step)
        step_layout.addStretch()
        btn_refresh = QPushButton("↻ Refresh")
        btn_refresh.clicked.connect(self.refresh_requested.emit)
        step_layout.addWidget(btn_refresh)
        layout.addLayout(step_layout)

        # Jog buttons
        jog_grid = QGridLayout()
        jog_grid.setSpacing(6)

        jog_btn_style = """
            QPushButton {
                font-size: 16px;
                font-weight: bold;
                min-width: 50px;
                min-height: 35px;
            }
        """

        for row, (axis, label_text) in enumerate([
            (Axis.X, "X:"), (Axis.Y, "Y:"), (Axis.Z, "Z:")
        ]):
            lbl = QLabel(label_text)
            lbl.setStyleSheet("font-weight: bold; font-size: 14px;")
            jog_grid.addWidget(lbl, row, 0)

            btn_minus = QPushButton("−")
            btn_minus.setStyleSheet(jog_btn_style)
            btn_minus.clicked.connect(lambda checked=False, a=axis: self._jog(a, -1))
            jog_grid.addWidget(btn_minus, row, 1)

            btn_plus = QPushButton("+")
            btn_plus.setStyleSheet(jog_btn_style)
            btn_plus.clicked.connect(lambda checked=False, a=axis: self._jog(a, 1))
            jog_grid.addWidget(btn_plus, row, 2)

        jog_grid.setColumnStretch(3, 1)
        layout.addLayout(jog_grid)

        # Separator
        separator = QLabel("")
        separator.setStyleSheet("background-color: #3a3a3a; min-height: 1px; max-height: 1px;")
        layout.addWidget(separator)

        # Absolute position entry
        goto_layout = QHBoxLayout()
        goto_layout.setSpacing(8)

        goto_layout.addWidget(QLabel("Go to:"))

        goto_layout.addWidget(QLabel("X:"))
        self.spin_goto_x = QDoubleSpinBox()
        self.spin_goto_x.setRange(0.0, 300.0)
        self.spin_goto_x.setValue(200.0)
        self.spin_goto_x.setDecimals(2)
        self.spin_goto_x.setMaximumWidth(80)
        goto_layout.addWidget(self.spin_goto_x)

        goto_layout.addWidget(QLabel("Y:"))
        self.spin_goto_y = QDoubleSpinBox()
        self.spin_goto_y.setRange(0.0, 300.0)
        self.spin_goto_y.setValue(200.0)
        self.spin_goto_y.setDecimals(2)
        self.spin_goto_y.setMaximumWidth(80)
        goto_layout.addWidget(self.spin_goto_y)

        goto_layout.addWidget(QLabel("Z:"))
        self.spin_goto_z = QDoubleSpinBox()
        self.spin_goto_z.setRange(0.0, 300.0)
        self.spin_goto_z.setValue(200.0)
        self.spin_goto_z.setDecimals(2)
        self.spin_goto_z.setMaximumWidth(80)
        goto_layout.addWidget(self.spin_goto_z)

        btn_goto = QPushButton("Go")
        btn_goto.setStyleSheet("font-weight: bold; min-width: 60px;")
        btn_goto.clicked.connect(self._on_goto)
        goto_layout.addWidget(btn_goto)

        goto_layout.addStretch()
        layout.addLayout(goto_layout)

    def _jog(self, axis: Axis, direction: int):
        step = self.spin_step.value() * direction
        self.jog_requested.emit(axis, step)

    def _on_goto(self):
        target = Position(
            x=self.spin_goto_x.value(),
            y=self.spin_goto_y.value(),
            z=self.spin_goto_z.value(),
        )
        self.goto_requested.emit(target)

    def update_position(self, pos: Position):
        self.pos_label.setText(f"Position: X={pos.x:.2f} Y={pos.y:.2f} Z={pos.z:.2f}")
        self.spin_goto_x.setValue(pos.x)
        self.spin_goto_y.setValue(pos.y)
        self.spin_goto_z.setValue(pos.z)
