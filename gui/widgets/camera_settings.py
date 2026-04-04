from PySide6.QtWidgets import (
    QGroupBox, QGridLayout, QLabel, QDoubleSpinBox, QPushButton,
    QComboBox, QHBoxLayout,
)
from PySide6.QtCore import Signal


class CameraSettingsPanel(QGroupBox):
    """Camera settings panel (exposure, gain, white balance)."""

    exposure_changed = Signal(float)           # exposure in seconds
    gain_changed = Signal(float)               # gain in dB
    white_balance_changed = Signal(float, float, float)  # R, G, B

    def __init__(self, parent=None):
        super().__init__("Camera Settings", parent)
        self.setStyleSheet("QGroupBox { font-weight: bold; }")

        layout = QGridLayout(self)
        layout.setSpacing(8)

        # Exposure row
        layout.addWidget(QLabel("Exposure (ms):"), 0, 0)
        self.spin_exposure = QDoubleSpinBox()
        self.spin_exposure.setRange(1.0, 5000.0)
        self.spin_exposure.setValue(100.0)
        self.spin_exposure.setSingleStep(10.0)
        self.spin_exposure.setDecimals(1)
        self.spin_exposure.setMinimumWidth(80)
        layout.addWidget(self.spin_exposure, 0, 1)
        btn_set_exposure = QPushButton("Set")
        btn_set_exposure.clicked.connect(self._on_set_exposure)
        layout.addWidget(btn_set_exposure, 0, 2)

        # Gain row
        layout.addWidget(QLabel("Gain (dB):"), 1, 0)
        self.spin_gain = QDoubleSpinBox()
        self.spin_gain.setRange(0.0, 48.0)
        self.spin_gain.setValue(0.0)
        self.spin_gain.setSingleStep(1.0)
        self.spin_gain.setDecimals(1)
        self.spin_gain.setMinimumWidth(80)
        layout.addWidget(self.spin_gain, 1, 1)
        btn_set_gain = QPushButton("Set")
        btn_set_gain.clicked.connect(self._on_set_gain)
        layout.addWidget(btn_set_gain, 1, 2)

        # White Balance preset row
        layout.addWidget(QLabel("White Balance:"), 2, 0)
        self.combo_wb = QComboBox()
        self.combo_wb.addItems(["Default", "Warm", "Cool", "Reduce NIR", "Custom"])
        self.combo_wb.currentTextChanged.connect(self._on_wb_preset_changed)
        layout.addWidget(self.combo_wb, 2, 1, 1, 2)

        # RGB on one row
        rgb_layout = QHBoxLayout()
        rgb_layout.setSpacing(4)
        rgb_layout.addWidget(QLabel("R:"))
        self.spin_wb_r = QDoubleSpinBox()
        self.spin_wb_r.setRange(0.1, 4.0)
        self.spin_wb_r.setValue(1.0)
        self.spin_wb_r.setSingleStep(0.1)
        self.spin_wb_r.setDecimals(2)
        self.spin_wb_r.setMaximumWidth(65)
        rgb_layout.addWidget(self.spin_wb_r)

        rgb_layout.addWidget(QLabel("G:"))
        self.spin_wb_g = QDoubleSpinBox()
        self.spin_wb_g.setRange(0.1, 4.0)
        self.spin_wb_g.setValue(1.0)
        self.spin_wb_g.setSingleStep(0.1)
        self.spin_wb_g.setDecimals(2)
        self.spin_wb_g.setMaximumWidth(65)
        rgb_layout.addWidget(self.spin_wb_g)

        rgb_layout.addWidget(QLabel("B:"))
        self.spin_wb_b = QDoubleSpinBox()
        self.spin_wb_b.setRange(0.1, 4.0)
        self.spin_wb_b.setValue(1.0)
        self.spin_wb_b.setSingleStep(0.1)
        self.spin_wb_b.setDecimals(2)
        self.spin_wb_b.setMaximumWidth(65)
        rgb_layout.addWidget(self.spin_wb_b)
        rgb_layout.addStretch()

        layout.addLayout(rgb_layout, 3, 0, 1, 3)

        # Apply WB button
        btn_apply_wb = QPushButton("Apply White Balance")
        btn_apply_wb.clicked.connect(self._on_apply_white_balance)
        layout.addWidget(btn_apply_wb, 4, 0, 1, 3)

    def _on_set_exposure(self):
        exposure_ms = self.spin_exposure.value()
        exposure_sec = exposure_ms / 1000.0
        self.exposure_changed.emit(exposure_sec)

    def _on_set_gain(self):
        self.gain_changed.emit(self.spin_gain.value())

    def _on_wb_preset_changed(self, preset: str):
        presets = {
            "Default": (1.0, 1.0, 1.0),
            "Warm": (1.0, 0.9, 0.7),
            "Cool": (0.9, 1.0, 1.2),
            "Reduce NIR": (0.6, 0.8, 1.0),
            "Custom": None,
        }
        if preset in presets and presets[preset] is not None:
            r, g, b = presets[preset]
            self.spin_wb_r.setValue(r)
            self.spin_wb_g.setValue(g)
            self.spin_wb_b.setValue(b)
            self._on_apply_white_balance()

    def _on_apply_white_balance(self):
        self.white_balance_changed.emit(
            self.spin_wb_r.value(),
            self.spin_wb_g.value(),
            self.spin_wb_b.value(),
        )
