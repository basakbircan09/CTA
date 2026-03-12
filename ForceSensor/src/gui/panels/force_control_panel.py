"""
Force Sensor Control Panel

DeviceControlPanel-based controller for I-7016 DCON force sensor.
Uses DeviceRegistry pattern for unified architecture.

Layout: Connection controls, live force value (Newtons), real-time plot, safety warnings.
"""

from collections import deque
from typing import Dict, Any, Optional

from PySide6.QtWidgets import (
    QVBoxLayout, QHBoxLayout, QLabel, QGroupBox, QGridLayout,
    QPushButton, QSpinBox, QWidget, QScrollArea, QMessageBox
)
from PySide6.QtCore import Qt, Signal, Slot

import pyqtgraph as pg

from gui.base.device_control_base import DeviceControlPanel, FormSerializationMixin, ControlPanelState
from devices import DeviceRegistry, CommandResult


class ForceControlPanel(DeviceControlPanel, FormSerializationMixin):
    """Device control panel for I-7016 force sensor.

    Uses DeviceRegistry pattern for unified device communication.
    Live streaming force data with PyQtGraph plot.
    """

    # Internal signal for thread-safe UI updates from device callbacks
    _device_result = Signal(str, object)  # command_name, CommandResult

    # Max samples in rolling buffer (at 20 Hz, 2000 = 100s of data)
    MAX_SAMPLES = 2000

    def __init__(
        self,
        device_registry: DeviceRegistry = None,
        parent=None
    ):
        # Get device from registry
        self._device = None
        if device_registry is not None:
            self._device = device_registry.get("force_sensor")

        # State tracking
        self._connected = False
        self._streaming = False

        # Data buffer for plot (stores calibrated Newton values)
        self._samples = deque(maxlen=self.MAX_SAMPLES)

        # Safety thresholds from device config
        self._warning_threshold = 3.5
        self._critical_threshold = 4.5
        if self._device:
            self._warning_threshold = self._device.warning_threshold
            self._critical_threshold = self._device.critical_threshold

        # Track whether critical popup has been shown (avoid spamming)
        self._critical_popup_shown = False

        # Initialize base (calls _build_ui)
        super().__init__(parent=parent)

        # Connect thread-safe result signal
        self._device_result.connect(self._on_device_result)

        # Connect streaming signal from device
        if self._device:
            self._device.signals.force_updated.connect(self._on_force_sample)

    # --- DeviceControlPanel ABC implementation ---

    def _get_device_name(self) -> str:
        return "force_sensor"

    def _serialize_parameters(self) -> Dict[str, Any]:
        return {
            "hz": self._hz_spin.value(),
        }

    def _validate_parameters(self, params: Dict[str, Any]) -> tuple[bool, Optional[str]]:
        hz = params.get("hz", 20)
        if hz < 1 or hz > 200:
            return False, "Hz must be between 1 and 200"
        return True, None

    # --- UI Construction ---

    def _build_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)

        # Scroll area for collapsible splitter support
        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        scroll_area.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)

        scroll_content = QWidget()
        layout = QVBoxLayout(scroll_content)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(8)

        # --- Connection group ---
        conn_group = QGroupBox("Connection")
        conn_layout = QHBoxLayout(conn_group)

        self._connect_btn = QPushButton("Connect")
        self._connect_btn.clicked.connect(self._on_connect_clicked)
        conn_layout.addWidget(self._connect_btn)

        self._disconnect_btn = QPushButton("Disconnect")
        self._disconnect_btn.setEnabled(False)
        self._disconnect_btn.clicked.connect(self._on_disconnect_clicked)
        conn_layout.addWidget(self._disconnect_btn)

        self._conn_status_label = QLabel("Disconnected")
        self._conn_status_label.setStyleSheet("color: gray; font-weight: bold;")
        conn_layout.addWidget(self._conn_status_label)
        conn_layout.addStretch()

        layout.addWidget(conn_group)

        # --- Live Force Value ---
        value_group = QGroupBox("Force Reading")
        value_layout = QVBoxLayout(value_group)

        self._value_label = QLabel("--- N")
        self._value_label.setStyleSheet("font-size: 48px; font-weight: 700;")
        self._value_label.setAlignment(Qt.AlignCenter)
        value_layout.addWidget(self._value_label)

        self._sub_label = QLabel(f"Safe range: 0–{self._critical_threshold:.1f} N")
        self._sub_label.setAlignment(Qt.AlignCenter)
        self._sub_label.setStyleSheet("color: #888; font-size: 9pt;")
        value_layout.addWidget(self._sub_label)

        layout.addWidget(value_group)

        # --- Controls ---
        ctrl_group = QGroupBox("Stream Control")
        ctrl_layout = QGridLayout(ctrl_group)

        # Hz selector
        ctrl_layout.addWidget(QLabel("Poll Rate:"), 0, 0)
        self._hz_spin = QSpinBox()
        self._hz_spin.setRange(1, 200)
        self._hz_spin.setValue(20)
        self._hz_spin.setSuffix(" Hz")
        ctrl_layout.addWidget(self._hz_spin, 0, 1)

        # Buttons row
        btn_layout = QHBoxLayout()

        self._start_stream_btn = QPushButton("Start Stream")
        self._start_stream_btn.setEnabled(False)
        self._start_stream_btn.setStyleSheet(
            "QPushButton { background-color: #2d8659; color: white; font-weight: bold; padding: 8px; }"
        )
        self._start_stream_btn.clicked.connect(self._on_start_stream_clicked)
        btn_layout.addWidget(self._start_stream_btn)

        self._stop_stream_btn = QPushButton("Stop Stream")
        self._stop_stream_btn.setEnabled(False)
        self._stop_stream_btn.setStyleSheet(
            "QPushButton { background-color: #c0392b; color: white; font-weight: bold; padding: 8px; }"
        )
        self._stop_stream_btn.clicked.connect(self._on_stop_stream_clicked)
        btn_layout.addWidget(self._stop_stream_btn)

        ctrl_layout.addLayout(btn_layout, 1, 0, 1, 2)

        # Single read button
        self._read_once_btn = QPushButton("Read Once")
        self._read_once_btn.setEnabled(False)
        self._read_once_btn.clicked.connect(self._on_read_once_clicked)
        ctrl_layout.addWidget(self._read_once_btn, 2, 0, 1, 2)

        layout.addWidget(ctrl_group)

        # --- Live Plot ---
        plot_group = QGroupBox("Force vs Time")
        plot_layout = QVBoxLayout(plot_group)

        pg.setConfigOptions(antialias=True)
        self._plot_widget = pg.PlotWidget()
        self._plot_widget.setLabel("left", "Force", units="N")
        self._plot_widget.setLabel("bottom", "Time", units="s")
        self._plot_widget.showGrid(x=True, y=True, alpha=0.3)
        self._curve = self._plot_widget.plot([], [], pen=pg.mkPen('#2196F3', width=2))

        plot_layout.addWidget(self._plot_widget)

        layout.addWidget(plot_group, stretch=1)

        # --- Status ---
        self._status_label = QLabel("Status: idle")
        self._status_label.setStyleSheet("color: #888; font-size: 9pt;")
        layout.addWidget(self._status_label)

        scroll_area.setWidget(scroll_content)
        main_layout.addWidget(scroll_area)

    # --- Button handlers ---

    def _on_connect_clicked(self):
        if not self._device:
            self._conn_status_label.setText("No device available")
            return
        self._connect_btn.setEnabled(False)
        self._conn_status_label.setText("Connecting...")
        self._device.connect_async(
            callback=lambda result: self._device_result.emit("connect", result)
        )

    def _on_disconnect_clicked(self):
        if not self._device:
            return
        self._disconnect_btn.setEnabled(False)
        self._conn_status_label.setText("Disconnecting...")
        self._device.disconnect_async(
            callback=lambda result: self._device_result.emit("disconnect", result)
        )

    def _on_start_stream_clicked(self):
        if not self._device:
            return
        hz = self._hz_spin.value()
        self._start_stream_btn.setEnabled(False)
        self._samples.clear()
        self._device.execute_async(
            "start_stream", {"hz": hz},
            callback=lambda result: self._device_result.emit("start_stream", result)
        )

    def _on_stop_stream_clicked(self):
        if not self._device:
            return
        self._stop_stream_btn.setEnabled(False)
        self._device.execute_async(
            "stop_stream", {},
            callback=lambda result: self._device_result.emit("stop_stream", result)
        )

    def _on_read_once_clicked(self):
        if not self._device:
            return
        self._read_once_btn.setEnabled(False)
        self._device.execute_async(
            "read_force", {},
            callback=lambda result: self._device_result.emit("read_force", result)
        )

    # --- Streaming data handler (Qt signal, already on main thread) ---

    @Slot(float, float)
    def _on_force_sample(self, t: float, force_n: float):
        """Handle streaming force data (already calibrated to Newtons)."""
        self._samples.append((t, force_n))

        # Update value display with directional arrow
        arrow = "\u2193" if force_n >= 0 else "\u2191"  # ↓ compression, ↑ tension
        self._value_label.setText(f"{arrow} {abs(force_n):.3f} N")

        # Apply warning colors based on thresholds
        abs_force = abs(force_n)
        if abs_force >= self._critical_threshold:
            self._value_label.setStyleSheet(
                "font-size: 48px; font-weight: 700; color: #F44336;"  # Red
            )
            # Show popup once per critical exceedance (reset when below threshold)
            if not self._critical_popup_shown:
                self._critical_popup_shown = True
                QMessageBox.warning(
                    self, "Force Limit Exceeded",
                    f"Force reading {force_n:.3f} N exceeds critical threshold "
                    f"({self._critical_threshold:.1f} N)!\n\n"
                    f"Risk of sensor damage. Take immediate action."
                )
        elif abs_force >= self._warning_threshold:
            self._value_label.setStyleSheet(
                "font-size: 48px; font-weight: 700; color: #F44336;"  # Red
            )
            self._critical_popup_shown = False
        else:
            self._value_label.setStyleSheet(
                "font-size: 48px; font-weight: 700; color: #2196F3;"  # Blue (normal)
            )
            self._critical_popup_shown = False

        # Update plot
        x = [tt for tt, _ in self._samples]
        y = [f for _, f in self._samples]
        self._curve.setData(x, y)

    # --- Thread-safe result handling ---

    @Slot(str, object)
    def _on_device_result(self, command: str, result: CommandResult):
        """Handle device command results on the main thread."""
        if command == "connect":
            if result.success:
                self._connected = True
                self._conn_status_label.setText("Connected")
                self._conn_status_label.setStyleSheet("color: green; font-weight: bold;")
                self._connect_btn.setEnabled(False)
                self._disconnect_btn.setEnabled(True)
                self._start_stream_btn.setEnabled(True)
                self._read_once_btn.setEnabled(True)

                data = result.data or {}
                port = data.get("port", "?")
                self._status_label.setText(f"Status: connected on {port}")
            else:
                self._conn_status_label.setText(f"Failed: {result.error_message}")
                self._conn_status_label.setStyleSheet("color: red; font-weight: bold;")
                self._connect_btn.setEnabled(True)

        elif command == "disconnect":
            self._connected = False
            self._streaming = False
            self._conn_status_label.setText("Disconnected")
            self._conn_status_label.setStyleSheet("color: gray; font-weight: bold;")
            self._connect_btn.setEnabled(True)
            self._disconnect_btn.setEnabled(False)
            self._start_stream_btn.setEnabled(False)
            self._stop_stream_btn.setEnabled(False)
            self._read_once_btn.setEnabled(False)
            self._value_label.setText("--- N")
            self._value_label.setStyleSheet("font-size: 48px; font-weight: 700;")
            self._sub_label.setText(f"Safe range: 0–{self._critical_threshold:.1f} N")
            self._status_label.setText("Status: disconnected")

        elif command == "start_stream":
            if result.success:
                self._streaming = True
                self._start_stream_btn.setEnabled(False)
                self._stop_stream_btn.setEnabled(True)
                self._read_once_btn.setEnabled(False)
                hz = (result.data or {}).get("hz", "?")
                self._status_label.setText(f"Status: streaming at {hz} Hz")
            else:
                self._start_stream_btn.setEnabled(True)
                self._status_label.setText(f"Status: stream failed: {result.error_message}")

        elif command == "stop_stream":
            self._streaming = False
            self._start_stream_btn.setEnabled(True)
            self._stop_stream_btn.setEnabled(False)
            self._read_once_btn.setEnabled(True)
            self._status_label.setText("Status: stream stopped")

        elif command == "read_force":
            self._read_once_btn.setEnabled(True)
            if result.success:
                data = result.data or {}
                raw = data.get("raw", 0.0)
                # Convert raw to Newton using device calibration
                if self._device:
                    force_n = self._device.raw_to_newton(raw)
                else:
                    force_n = -1.996 * (raw - 0.0360)  # Fallback
                arrow = "\u2193" if force_n >= 0 else "\u2191"
                self._value_label.setText(f"{arrow} {abs(force_n):.3f} N")
                # Apply warning color
                abs_force = abs(force_n)
                if abs_force >= self._warning_threshold:
                    self._value_label.setStyleSheet(
                        "font-size: 48px; font-weight: 700; color: #F44336;"
                    )
                else:
                    self._value_label.setStyleSheet(
                        "font-size: 48px; font-weight: 700; color: #2196F3;"
                    )
                self._status_label.setText(f"Status: single read OK ({force_n:.3f} N)")
            else:
                self._status_label.setText(f"Status: read failed: {result.error_message}")
