"""
Camera control panel widget.
"""

from __future__ import annotations

from typing import Optional

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QDoubleSpinBox,
    QGroupBox,
    QHBoxLayout,
    QPushButton,
    QSlider,
    QVBoxLayout,
    QWidget,
)


class CameraControlPanel(QGroupBox):
    """Control panel for exposure, gain, and acquisition actions."""

    exposureChanged = Signal(float)
    gainChanged = Signal(float)
    startRequested = Signal()
    stopRequested = Signal()
    snapshotRequested = Signal()

    def __init__(
        self,
        parent: Optional[QWidget] = None,
        exposure_bounds_ms: tuple[float, float] = (0.1, 1000.0),
        gain_bounds_db: tuple[float, float] = (0.0, 24.0),
    ) -> None:
        super().__init__("Camera Controls", parent)
        self._exposure_bounds = exposure_bounds_ms
        self._gain_bounds = gain_bounds_db

        self._build_ui()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)

        # Exposure controls
        self._exposure_spin = QDoubleSpinBox(self)
        self._exposure_spin.setSuffix(" ms")
        self._exposure_spin.setRange(*self._exposure_bounds)
        self._exposure_spin.setDecimals(2)
        self._exposure_spin.setSingleStep(0.5)
        self._exposure_spin.setValue(30.0)
        self._exposure_spin.setToolTip(
            "Fine exposure control (ms). Adjust for brightness; slider offers coarse changes."
        )
        self._exposure_spin.setStatusTip("Adjust exposure precisely in milliseconds.")

        self._exposure_slider = QSlider(Qt.Horizontal, self)
        self._exposure_slider.setRange(0, 1000)
        self._exposure_slider.setValue(30)
        self._exposure_slider.setToolTip(
            "Coarse exposure adjustment. Range matches the spin box (0.1–1000 ms)."
        )
        self._exposure_slider.setStatusTip("Drag for quick exposure changes.")

        self._exposure_spin.valueChanged.connect(self._on_exposure_spin_changed)
        self._exposure_slider.valueChanged.connect(self._on_exposure_slider_changed)

        layout.addWidget(self._exposure_spin)
        layout.addWidget(self._exposure_slider)

        # Gain controls
        self._gain_spin = QDoubleSpinBox(self)
        self._gain_spin.setSuffix(" dB")
        self._gain_spin.setRange(*self._gain_bounds)
        self._gain_spin.setDecimals(1)
        self._gain_spin.setSingleStep(0.5)
        self._gain_spin.setValue(0.0)
        self._gain_spin.valueChanged.connect(self._on_gain_changed)
        self._gain_spin.setToolTip("Sensor gain in dB. Increase only when exposure cannot be lengthened.")
        self._gain_spin.setStatusTip("Modify analog gain; higher values add noise.")

        layout.addWidget(self._gain_spin)

        # Action buttons
        button_row = QHBoxLayout()
        self._start_button = QPushButton("Start Live", self)
        self._stop_button = QPushButton("Stop", self)
        self._snapshot_button = QPushButton("Snapshot", self)
        self._start_button.setToolTip("Begin live acquisition (Space). Applies current exposure/gain.")
        self._stop_button.setToolTip("Stop live acquisition (Space).")
        self._snapshot_button.setToolTip("Capture and save the latest frame (Ctrl+S).")
        self._start_button.setStatusTip("Start the live camera stream.")
        self._stop_button.setStatusTip("Stop the live camera stream.")
        self._snapshot_button.setStatusTip("Save the most recent frame to disk.")

        self._start_button.clicked.connect(self.startRequested.emit)
        self._stop_button.clicked.connect(self.stopRequested.emit)
        self._snapshot_button.clicked.connect(self.snapshotRequested.emit)

        button_row.addWidget(self._start_button)
        button_row.addWidget(self._stop_button)
        button_row.addWidget(self._snapshot_button)
        layout.addLayout(button_row)

    # ------------------------------------------------------------------ #
    # Public API
    # ------------------------------------------------------------------ #
    def set_exposure(self, exposure_ms: float) -> None:
        self._exposure_spin.blockSignals(True)
        self._exposure_slider.blockSignals(True)
        self._exposure_spin.setValue(exposure_ms)
        slider_value = self._exposure_to_slider(exposure_ms)
        self._exposure_slider.setValue(slider_value)
        self._exposure_spin.blockSignals(False)
        self._exposure_slider.blockSignals(False)

    def set_gain(self, gain_db: float) -> None:
        self._gain_spin.blockSignals(True)
        self._gain_spin.setValue(gain_db)
        self._gain_spin.blockSignals(False)

    def set_live_state(self, is_live: bool) -> None:
        self._start_button.setEnabled(not is_live)
        self._stop_button.setEnabled(is_live)

    def is_live(self) -> bool:
        """Check if camera is currently in live view mode."""
        return self._stop_button.isEnabled()

    # ------------------------------------------------------------------ #
    # Internal slots
    # ------------------------------------------------------------------ #
    def _on_exposure_spin_changed(self, value: float) -> None:
        slider_value = self._exposure_to_slider(value)
        self._exposure_slider.blockSignals(True)
        self._exposure_slider.setValue(slider_value)
        self._exposure_slider.blockSignals(False)
        self.exposureChanged.emit(value)

    def _on_exposure_slider_changed(self, slider_value: int) -> None:
        exposure_ms = self._slider_to_exposure(slider_value)
        self._exposure_spin.blockSignals(True)
        self._exposure_spin.setValue(exposure_ms)
        self._exposure_spin.blockSignals(False)
        self.exposureChanged.emit(exposure_ms)

    def _on_gain_changed(self, value: float) -> None:
        self.gainChanged.emit(value)

    def _exposure_to_slider(self, exposure_ms: float) -> int:
        min_ms, max_ms = self._exposure_bounds
        clamped = max(min(exposure_ms, max_ms), min_ms)
        normalized = (clamped - min_ms) / (max_ms - min_ms)
        return int(normalized * self._exposure_slider.maximum())

    def _slider_to_exposure(self, slider_value: int) -> float:
        min_ms, max_ms = self._exposure_bounds
        normalized = slider_value / max(self._exposure_slider.maximum(), 1)
        return min_ms + normalized * (max_ms - min_ms)

