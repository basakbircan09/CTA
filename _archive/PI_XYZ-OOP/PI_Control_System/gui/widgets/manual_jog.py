"""
Manual jog widget for relative axis movements.

Source: legacy/PI_Control_GUI/main_gui.py manual control
"""

from PySide6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QGridLayout,
                               QLabel, QPushButton, QDoubleSpinBox)
from PySide6.QtCore import Signal, Qt
from PySide6.QtGui import QFont

from ...core.models import Axis


class ManualJogWidget(QWidget):
    """Widget for manual relative jog movements.

    Emits jog_requested signal with axis and distance.
    Controller layer calls MotionService.move_axis_relative.

    Signals:
        jog_requested(axis, distance): User requested relative move
    """

    jog_requested = Signal(Axis, float)

    def __init__(self, default_step: float = 1.0, parent=None):
        super().__init__(parent)
        self._default_step = default_step
        self._setup_ui()

    def _setup_ui(self):
        """Build UI layout."""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)

        # Title
        title = QLabel("Manual Jog")
        title.setFont(QFont("Segoe UI", 12, QFont.Bold))
        title.setStyleSheet("color: #e2e8f0;")
        layout.addWidget(title)

        # Step size control
        step_layout = QHBoxLayout()
        step_label = QLabel("Step Size:")
        step_label.setStyleSheet("color: #cbd5e0; font-size: 10pt;")
        step_layout.addWidget(step_label)

        self.step_spinbox = QDoubleSpinBox()
        self.step_spinbox.setRange(0.01, 50.0)
        self.step_spinbox.setValue(self._default_step)
        self.step_spinbox.setSingleStep(0.1)
        self.step_spinbox.setDecimals(2)
        self.step_spinbox.setSuffix(" mm")
        self.step_spinbox.setStyleSheet("""
            QDoubleSpinBox {
                background: rgba(0,0,0,0.3);
                color: #63b3c2;
                border: 1px solid rgba(99, 179, 194, 0.3);
                border-radius: 4px;
                padding: 5px;
                font-size: 10pt;
            }
        """)
        step_layout.addWidget(self.step_spinbox)
        step_layout.addStretch()

        layout.addLayout(step_layout)

        # Jog buttons grid
        grid = QGridLayout()
        grid.setSpacing(10)

        self.jog_buttons = {}

        for row, axis in enumerate([Axis.X, Axis.Y, Axis.Z]):
            # Axis label
            axis_label = QLabel(f"{axis.value}:")
            axis_label.setFont(QFont("Segoe UI", 11, QFont.Bold))
            axis_label.setStyleSheet("color: #e2e8f0;")
            grid.addWidget(axis_label, row, 0)

            # Negative button (-)
            neg_btn = QPushButton(f"< -{axis.value}")
            neg_btn.setStyleSheet(self._button_style())
            neg_btn.clicked.connect(lambda checked, ax=axis: self._jog(ax, -self.step_spinbox.value()))
            grid.addWidget(neg_btn, row, 1)

            # Positive button (+)
            pos_btn = QPushButton(f"+{axis.value} >")
            pos_btn.setStyleSheet(self._button_style())
            pos_btn.clicked.connect(lambda checked, ax=axis: self._jog(ax, self.step_spinbox.value()))
            grid.addWidget(pos_btn, row, 2)

            self.jog_buttons[axis] = (neg_btn, pos_btn)

        layout.addLayout(grid)

    def _button_style(self) -> str:
        """Generate jog button stylesheet."""
        return """
            QPushButton {
                background-color: #3182ce;
                color: white;
                border: none;
                padding: 10px 20px;
                border-radius: 6px;
                font-size: 10pt;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #2c5aa0;
            }
            QPushButton:pressed {
                background-color: #2a4365;
            }
            QPushButton:disabled {
                background-color: #4a5568;
                color: #a0aec0;
            }
        """

    def _jog(self, axis: Axis, distance: float):
        """Emit jog request signal."""
        self.jog_requested.emit(axis, distance)

    def set_enabled(self, enabled: bool):
        """Enable/disable all jog buttons.

        Args:
            enabled: True to enable, False to disable
        """
        for neg_btn, pos_btn in self.jog_buttons.values():
            neg_btn.setEnabled(enabled)
            pos_btn.setEnabled(enabled)
        self.step_spinbox.setEnabled(enabled)
