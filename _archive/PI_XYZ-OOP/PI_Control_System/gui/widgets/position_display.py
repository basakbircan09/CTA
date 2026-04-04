"""
Position display widget showing current axis positions.

Source: legacy/PI_Control_GUI/main_gui.py position displays
"""

from PySide6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QLabel, QGridLayout
from PySide6.QtCore import Qt
from PySide6.QtGui import QFont

from ...core.models import Axis, Position


class PositionDisplayWidget(QWidget):
    """Widget displaying live axis positions.

    Controller layer updates this widget when position events arrive.
    No direct EventBus subscription - keeps widget testable.
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self._setup_ui()

    def _setup_ui(self):
        """Build UI layout."""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)

        # Title
        title = QLabel("Current Position")
        title.setFont(QFont("Segoe UI", 12, QFont.Bold))
        title.setStyleSheet("color: #e2e8f0;")
        layout.addWidget(title)

        # Position grid
        grid = QGridLayout()
        grid.setSpacing(10)

        self.position_labels = {}

        for row, axis in enumerate([Axis.X, Axis.Y, Axis.Z]):
            # Axis label
            axis_label = QLabel(f"{axis.value}:")
            axis_label.setFont(QFont("Segoe UI", 11, QFont.Bold))
            axis_label.setStyleSheet("color: #e2e8f0;")
            grid.addWidget(axis_label, row, 0)

            # Position value
            pos_label = QLabel("---")
            pos_label.setFont(QFont("Consolas", 14))
            pos_label.setStyleSheet("""
                QLabel {
                    color: #63b3c2;
                    background: rgba(0,0,0,0.3);
                    padding: 8px 15px;
                    border-radius: 4px;
                    min-width: 120px;
                }
            """)
            pos_label.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
            grid.addWidget(pos_label, row, 1)

            # Units
            unit_label = QLabel("mm")
            unit_label.setStyleSheet("color: #a0aec0; font-size: 10pt;")
            grid.addWidget(unit_label, row, 2)

            self.position_labels[axis] = pos_label

        layout.addLayout(grid)

    def update_position(self, position: Position):
        """Update displayed positions.

        Called by controller when POSITION_UPDATED event arrives.

        Args:
            position: New position snapshot
        """
        self.position_labels[Axis.X].setText(f"{position.x:.3f}")
        self.position_labels[Axis.Y].setText(f"{position.y:.3f}")
        self.position_labels[Axis.Z].setText(f"{position.z:.3f}")

    def clear_position(self):
        """Clear position display (e.g., after disconnect)."""
        for label in self.position_labels.values():
            label.setText("---")
