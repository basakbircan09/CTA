
from __future__ import annotations

import numpy as np
import pytest

pytest.importorskip("pytestqt")

from gui.camera_controls import CameraControlPanel
from gui.focus_assistant import FocusAssistantWidget
from gui.live_view import LiveViewWidget
from gui.main_window import MainWindow
from gui.settings_manager import SettingsManagerWidget
from gui.white_balance_panel import WhiteBalancePanel
from models.camera import CameraSettings, ROI
from models.frame import Frame


def test_live_view_updates_pixmap(qtbot):
    widget = LiveViewWidget()
    qtbot.addWidget(widget)
    frame = Frame(
        data=(np.ones((20, 30, 3), dtype=np.uint16) * 2000),
        timestamp_ns=0,
        frame_index=1,
    )
    widget.update_frame(frame)
    assert widget._image_label.pixmap() is not None


def test_camera_control_signals(qtbot):
    panel = CameraControlPanel()
    qtbot.addWidget(panel)

    with qtbot.waitSignal(panel.exposureChanged, timeout=1000):
        panel._exposure_slider.setValue(panel._exposure_slider.value() + 10)
    with qtbot.waitSignal(panel.gainChanged, timeout=1000):
        panel._gain_spin.setValue(panel._gain_spin.value() + 1.0)

    panel.set_live_state(True)
    assert not panel._start_button.isEnabled()
    assert panel._stop_button.isEnabled()
    panel.set_live_state(False)


def test_white_balance_panel_preset_updates(qtbot):
    panel = WhiteBalancePanel()
    qtbot.addWidget(panel)
    received = {}

    def capture(r, g, b):
        received["values"] = (r, g, b)

    panel.whiteBalanceChanged.connect(capture)
    panel.apply_preset("Reduce NIR")
    assert received["values"] == (0.6, 0.8, 1.0)
    panel.set_gains(1.1, 0.9, 0.8, notify=True)
    assert received["values"] == (1.1, 0.9, 0.8)


def test_focus_assistant_widget_updates(qtbot):
    widget = FocusAssistantWidget()
    qtbot.addWidget(widget)
    widget.update_score(250.0)
    assert abs(widget.score - 250.0) < 1e-6


def test_settings_manager_roundtrip(tmp_path, qtbot):
    widget = SettingsManagerWidget(presets_dir=tmp_path)
    qtbot.addWidget(widget)
    settings = CameraSettings(exposure_sec=0.02, gain_db=3.0, roi=ROI(0, 0, 100, 100))
    widget.save_preset("test", settings)
    loaded = widget.load_preset("test")
    assert loaded is not None
    assert loaded.exposure_sec == pytest.approx(settings.exposure_sec)
    assert widget.delete_preset("test") is True


def test_main_window_signal_forwarding(qtbot):
    window = MainWindow()
    qtbot.addWidget(window)
    captured = {"exposure": None}

    def on_exposure(value):
        captured["exposure"] = value

    window.exposureChanged.connect(on_exposure)
    window.control_panel.set_exposure(45.0)
    window.control_panel.exposureChanged.emit(45.0)
    assert captured["exposure"] == 45.0
