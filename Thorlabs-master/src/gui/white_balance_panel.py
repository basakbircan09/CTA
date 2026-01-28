"""
White balance control widget.
"""

from __future__ import annotations

from typing import Dict, Optional, Tuple

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QComboBox,
    QDoubleSpinBox,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QPushButton,
    QWidget,
)

WB_PRESETS: Dict[str, Tuple[float, float, float]] = {
    "Default": (1.0, 1.0, 1.0),
    "Reduce NIR": (0.6, 0.8, 1.0),
    "Strong NIR": (0.4, 0.7, 1.0),
    "Warm": (1.0, 0.9, 0.7),
    "Cool": (0.9, 1.0, 1.2),
    "Custom": (1.0, 1.0, 1.0),
}


class WhiteBalancePanel(QGroupBox):
    """Provides preset selection and manual RGB gain adjustment."""

    whiteBalanceChanged = Signal(float, float, float)
    presetSelected = Signal(str, tuple)
    resetRequested = Signal()

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__("White Balance", parent)
        self._build_ui()

    def _build_ui(self) -> None:
        layout = QFormLayout(self)

        self._preset_combo = QComboBox(self)
        for name in WB_PRESETS:
            self._preset_combo.addItem(name)
        self._preset_combo.currentTextChanged.connect(self._on_preset_changed)
        self._preset_combo.setToolTip(
            "Select a preset RGB gain combination. 'Custom' reflects manual adjustments."
        )
        self._preset_combo.setStatusTip("Choose a white balance preset for the current scene.")

        layout.addRow("Preset:", self._preset_combo)

        self._spin_r = self._make_spinbox()
        self._spin_g = self._make_spinbox()
        self._spin_b = self._make_spinbox()

        layout.addRow("Red gain:", self._spin_r)
        layout.addRow("Green gain:", self._spin_g)
        layout.addRow("Blue gain:", self._spin_b)

        button_row = QHBoxLayout()
        self._reset_button = QPushButton("Reset", self)
        button_row.addWidget(self._reset_button)
        self._reset_button.setToolTip("Restore default gains (1.0, 1.0, 1.0).")
        self._reset_button.setStatusTip("Reset white balance to factory defaults.")
        layout.addRow(button_row)

        self._reset_button.clicked.connect(self._on_reset_clicked)
        self._spin_r.valueChanged.connect(self._emit_manual_change)
        self._spin_g.valueChanged.connect(self._emit_manual_change)
        self._spin_b.valueChanged.connect(self._emit_manual_change)

        self.apply_preset("Default")

    def apply_preset(self, name: str) -> None:
        if name not in WB_PRESETS:
            return
        gains = WB_PRESETS[name]
        self._preset_combo.blockSignals(True)
        self._preset_combo.setCurrentText(name)
        self._preset_combo.blockSignals(False)
        self._set_gains(*gains, notify=True)
        self.presetSelected.emit(name, gains)

    def set_gains(self, red: float, green: float, blue: float, notify: bool = False) -> None:
        """Set RGB gains manually."""
        self._set_gains(red, green, blue, notify=notify)

    def _make_spinbox(self) -> QDoubleSpinBox:
        spin = QDoubleSpinBox(self)
        spin.setRange(0.1, 4.0)
        spin.setSingleStep(0.1)
        spin.setDecimals(2)
        spin.setValue(1.0)
        spin.setToolTip("Manual channel gain. Increase to boost the channel, decrease to reduce it.")
        spin.setStatusTip("Adjust individual RGB gains for manual white balance tuning.")
        return spin

    def _set_gains(self, red: float, green: float, blue: float, notify: bool) -> None:
        spins = (self._spin_r, self._spin_g, self._spin_b)
        values = (red, green, blue)
        for spin, value in zip(spins, values):
            spin.blockSignals(True)
            spin.setValue(value)
            spin.blockSignals(False)
        if notify:
            self.whiteBalanceChanged.emit(red, green, blue)

    def _on_preset_changed(self, name: str) -> None:
        if name not in WB_PRESETS:
            return
        self._set_gains(*WB_PRESETS[name], notify=True)
        self.presetSelected.emit(name, WB_PRESETS[name])

    def _emit_manual_change(self) -> None:
        self._preset_combo.blockSignals(True)
        self._preset_combo.setCurrentText("Custom")
        self._preset_combo.blockSignals(False)
        gains = (self._spin_r.value(), self._spin_g.value(), self._spin_b.value())
        self.whiteBalanceChanged.emit(*gains)

    def _on_reset_clicked(self) -> None:
        self.apply_preset("Default")
        self.resetRequested.emit()
