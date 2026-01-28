"""
Velocity control panel for per-axis velocity adjustment.

Source: legacy/PI_Control_GUI/main_gui.py velocity controls
"""

from PySide6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QLabel, QDoubleSpinBox, QGridLayout
from PySide6.QtCore import Signal, Qt
from PySide6.QtGui import QFont

from ...core.models import Axis


class VelocityPanel(QWidget):
    """Widget for per-axis velocity control.

    Emits velocity_changed signal when user adjusts values.
    Controller layer applies changes to MotionService.

    Signals:
        velocity_changed(axis, velocity): User changed velocity for an axis

    Source: legacy/scripts/GUI601.py:274-306 (spinbox-only design)
    """

    velocity_changed = Signal(Axis, float)

    def __init__(self, max_velocity: float = 20.0, default_velocity: float = 10.0, parent=None):
        super().__init__(parent)
        self._max_velocity = max_velocity
        self._default_velocity = default_velocity
        self._setup_ui()

    def _setup_ui(self):
        """Build UI layout."""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)

        # Title
        title = QLabel("Velocity Settings")
        title.setFont(QFont("Segoe UI", 12, QFont.Bold))
        title.setStyleSheet("color: #e2e8f0;")
        layout.addWidget(title)

        # Grid for per-axis controls
        grid = QGridLayout()
        grid.setSpacing(10)

        self.velocity_spinboxes = {}

        for col, axis in enumerate([Axis.X, Axis.Y, Axis.Z]):
            # Axis label
            axis_label = QLabel(f"{axis.value}-Axis")
            axis_label.setAlignment(Qt.AlignCenter)
            axis_label.setFont(QFont("Segoe UI", 11, QFont.Bold))
            axis_label.setStyleSheet("color: #e2e8f0;")
            grid.addWidget(axis_label, 0, col)

            # Spinbox (actual mm/s value)
            spinbox = QDoubleSpinBox()
            spinbox.setRange(0.1, self._max_velocity)
            spinbox.setValue(self._default_velocity)
            spinbox.setSingleStep(0.5)
            spinbox.setDecimals(1)
            spinbox.setSuffix(" mm/s")
            spinbox.setStyleSheet("""
                QDoubleSpinBox {
                    background: rgba(0,0,0,0.3);
                    color: #63b3c2;
                    border: 1px solid rgba(99, 179, 194, 0.3);
                    border-radius: 4px;
                    padding: 5px;
                    font-size: 11pt;
                }
            """)
            grid.addWidget(spinbox, 1, col)

            # Max indicator
            max_label = QLabel(f"Max: {self._max_velocity} mm/s")
            max_label.setAlignment(Qt.AlignCenter)
            max_label.setStyleSheet("color: #a0aec0; font-size: 10px;")
            grid.addWidget(max_label, 2, col)

            # Emit signal when value changes
            spinbox.valueChanged.connect(lambda val, ax=axis: self.velocity_changed.emit(ax, val))

            self.velocity_spinboxes[axis] = spinbox

        layout.addLayout(grid)

    def set_velocity(self, axis: Axis, velocity: float):
        """Set velocity for an axis (programmatic update).

        Args:
            axis: Target axis
            velocity: Velocity in mm/s
        """
        spinbox = self.velocity_spinboxes[axis]

        # Block signals to avoid emission during programmatic set
        spinbox.blockSignals(True)
        spinbox.setValue(velocity)
        spinbox.blockSignals(False)

    def get_velocity(self, axis: Axis) -> float:
        """Get current velocity setting for an axis.

        Args:
            axis: Target axis

        Returns:
            Velocity in mm/s
        """
        return self.velocity_spinboxes[axis].value()

    def set_enabled(self, enabled: bool):
        """Enable/disable all controls.

        Args:
            enabled: True to enable, False to disable
        """
        for spinbox in self.velocity_spinboxes.values():
            spinbox.setEnabled(enabled)
