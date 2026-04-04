"""
GUI widget for displaying focus metric readings.
"""

from __future__ import annotations

from typing import Optional

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QLabel, QProgressBar, QVBoxLayout, QWidget


class FocusAssistantWidget(QWidget):
    """Displays current focus score to aid manual focusing."""

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self._score = 0.0

        self._label = QLabel("Focus score: 0.0", self)
        self._label.setAlignment(Qt.AlignCenter)
        self._label.setToolTip("Higher values indicate sharper edges. Aim for the highest score while focusing.")

        self._progress = QProgressBar(self)
        self._progress.setRange(0, 100)
        self._progress.setValue(0)
        self._progress.setFormat("%p%")
        self._progress.setToolTip("Visual indicator of focus quality. 100% corresponds to the best recent score.")

        layout = QVBoxLayout(self)
        layout.addWidget(self._label)
        layout.addWidget(self._progress)
        self.setToolTip("Monitor focus quality while adjusting the lens.")

    def update_score(self, score: float) -> None:
        """Update the displayed focus score."""
        self._score = score
        self._label.setText(f"Focus score: {score:.2f}")
        normalized = max(min(score / 1000.0, 1.0), 0.0)
        self._progress.setValue(int(normalized * 100))

    @property
    def score(self) -> float:
        return self._score
