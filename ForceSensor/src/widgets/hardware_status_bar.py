"""
Hardware Status Bar Widget

Displays real-time hardware connection status for all devices.
Self-contained widget that handles its own status updates.

Usage:
    status_bar = HardwareStatusBar()
    supervisor_service.status_updated.connect(status_bar.update_status)
    toolbar.addWidget(status_bar)
"""

import logging
import time
from typing import Dict, Optional, Callable
from PySide6.QtWidgets import (
    QWidget, QHBoxLayout, QLabel, QSizePolicy, QToolBar
)
from PySide6.QtCore import Signal, Slot

logger = logging.getLogger(__name__)


class DeviceStatusIndicator(QWidget):
    """Single device status indicator with LED, name, status text, and circuit breaker state."""

    # LED colors
    COLOR_CONNECTED = '#4CAF50'    # Green
    COLOR_DISCONNECTED = '#F44336'  # Red
    COLOR_READY = '#FFC107'         # Amber
    COLOR_OFFLINE = '#888888'       # Gray

    # Circuit breaker colors
    CIRCUIT_CLOSED = '#4CAF50'      # Green - healthy
    CIRCUIT_HALF_OPEN = '#FFC107'   # Amber - testing recovery
    CIRCUIT_OPEN = '#F44336'        # Red - failing fast

    def __init__(self, device_id: str, display_name: str, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.device_id = device_id
        self.display_name = display_name
        self._live_value_active = False

        self._setup_ui()

    def _setup_ui(self):
        layout = QHBoxLayout(self)
        layout.setContentsMargins(8, 0, 8, 0)
        layout.setSpacing(4)

        # LED indicator
        self.led = QLabel("●")
        self.led.setStyleSheet(f"color: {self.COLOR_OFFLINE}; font-size: 14pt;")
        self.led.setToolTip(f"{self.display_name} - Initializing...")
        layout.addWidget(self.led)

        # Device name
        name_label = QLabel(self.display_name)
        name_label.setStyleSheet("font-size: 10pt;")
        layout.addWidget(name_label)

        # Status text
        self.status_label = QLabel("--")
        self.status_label.setStyleSheet("color: #666; font-size: 9pt; min-width: 80px;")
        layout.addWidget(self.status_label)

        # Circuit breaker indicator (small, shows only when not CLOSED)
        self.circuit_label = QLabel("")
        self.circuit_label.setStyleSheet("font-size: 8pt;")
        self.circuit_label.setVisible(False)  # Hidden when circuit is healthy
        layout.addWidget(self.circuit_label)

    def update_status(self, state: str, hw_connected: bool, hardware_ok: bool,
                      hardware_error: Optional[str] = None, restart_count: int = 0,
                      circuit_state: str = "CLOSED", circuit_failures: int = 0):
        """Update the indicator based on device status.

        Args:
            state: Wrapper state (stopped, starting, ready, running, unhealthy, error)
            hw_connected: Whether hardware connection was established
            hardware_ok: Whether hardware probe succeeded (new field from wrapper)
            hardware_error: Error message if hardware probe failed
            restart_count: Number of auto-restart attempts
            circuit_state: Circuit breaker state (CLOSED, HALF_OPEN, OPEN)
            circuit_failures: Consecutive failure count
        """
        # Determine LED color and status text
        if state in ('stopped',):
            color = self.COLOR_OFFLINE
            status_text = "Offline"
            status_style = "color: #888;"
        elif state in ('starting', 'restarting'):
            color = self.COLOR_READY
            status_text = "Starting..."
            status_style = "color: #FFC107;"
        elif state in ('unhealthy', 'error'):
            color = self.COLOR_DISCONNECTED
            status_text = "Error"
            status_style = "color: #F44336; font-weight: bold;"
        elif state in ('ready', 'running'):
            if hw_connected and hardware_ok:
                color = self.COLOR_CONNECTED
                status_text = "Connected"
                status_style = "color: #4CAF50; font-weight: bold;"
            elif hw_connected and not hardware_ok:
                # Hardware was connected but probe failed (USB disconnected)
                color = self.COLOR_DISCONNECTED
                status_text = "Disconnected"
                status_style = "color: #F44336; font-weight: bold;"
            else:
                color = self.COLOR_READY
                status_text = "Ready"
                status_style = "color: #FFC107;"
        else:
            color = self.COLOR_OFFLINE
            status_text = state.title() if state else "--"
            status_style = "color: #888;"

        # Update LED (always, regardless of live value)
        self.led.setStyleSheet(f"color: {color}; font-size: 14pt;")

        # If device is no longer connected/ready, clear live value override
        if state not in ('ready', 'running') or not hw_connected:
            self._live_value_active = False

        # Update status label — skip if live value is being shown
        if not self._live_value_active:
            self.status_label.setText(status_text)
            self.status_label.setStyleSheet(f"{status_style} font-size: 9pt; min-width: 80px;")

        # Build tooltip
        tooltip_lines = [self.display_name]

        if state == 'stopped':
            tooltip_lines.append("Wrapper: Not running")
        else:
            tooltip_lines.append(f"Wrapper: {state.title()}")

        if state in ('ready', 'running'):
            if hw_connected and hardware_ok:
                tooltip_lines.append("Hardware: Connected ✓")
            elif hw_connected and not hardware_ok:
                tooltip_lines.append("Hardware: USB Disconnected!")
                if hardware_error:
                    # Truncate long error messages
                    error_preview = hardware_error[:50] + "..." if len(hardware_error) > 50 else hardware_error
                    tooltip_lines.append(f"Error: {error_preview}")
            else:
                tooltip_lines.append("Hardware: Not connected")
                tooltip_lines.append("(Click Connect in device panel)")

        if restart_count > 0:
            tooltip_lines.append(f"Auto-restarts: {restart_count}/4")

        if state == 'restarting':
            tooltip_lines.append("(Recovery in progress...)")
        elif state == 'unhealthy':
            tooltip_lines.append("(Wrapper unresponsive)")

        # Add circuit breaker info to tooltip if not healthy
        if circuit_state != "CLOSED":
            tooltip_lines.append(f"Circuit: {circuit_state} ({circuit_failures} failures)")

        self.led.setToolTip("\n".join(tooltip_lines))

        # Update circuit breaker indicator
        self._update_circuit_indicator(circuit_state, circuit_failures)

    def _update_circuit_indicator(self, circuit_state: str, circuit_failures: int):
        """Update the circuit breaker indicator display."""
        if circuit_state == "CLOSED":
            # Hidden when healthy
            self.circuit_label.setVisible(False)
        elif circuit_state == "HALF_OPEN":
            # Amber - testing recovery
            self.circuit_label.setText("⚡")
            self.circuit_label.setStyleSheet(
                f"color: {self.CIRCUIT_HALF_OPEN}; font-size: 10pt;"
            )
            self.circuit_label.setToolTip(
                f"Circuit Breaker: HALF_OPEN\n"
                f"Testing recovery after {circuit_failures} failures"
            )
            self.circuit_label.setVisible(True)
        elif circuit_state == "OPEN":
            # Red - failing fast
            self.circuit_label.setText("⚡")
            self.circuit_label.setStyleSheet(
                f"color: {self.CIRCUIT_OPEN}; font-size: 10pt; font-weight: bold;"
            )
            self.circuit_label.setToolTip(
                f"Circuit Breaker: OPEN\n"
                f"{circuit_failures} consecutive failures\n"
                f"Commands are being rejected"
            )
            self.circuit_label.setVisible(True)

    def set_live_value(self, text: str):
        """Override the status text with a live value (e.g., force reading).

        The live value replaces the normal status text while active.
        Call clear_live_value() or update_status() to restore normal display.
        """
        self._live_value_active = True
        self.status_label.setText(text)
        self.status_label.setStyleSheet(
            "color: #2196F3; font-size: 9pt; min-width: 80px; font-weight: bold;"
        )

    def clear_live_value(self):
        """Clear the live value override, restoring normal status display."""
        self._live_value_active = False

    def is_connected(self) -> bool:
        """Check if this device shows as connected."""
        # Live value means connected and streaming
        if self._live_value_active:
            return True
        return self.status_label.text() == "Connected"


class HardwareStatusBar(QWidget):
    """
    Hardware status bar showing connection state for all devices.

    Signals:
        connection_changed: Emitted when any device connection state changes
            Args: (device_id: str, connected: bool)
    """

    connection_changed = Signal(str, bool)  # device_id, connected

    # Device configuration
    DEVICES = {
        "gamry": "Gamry",
        "pi_xyz": "PI XYZ",
        "thorlabs": "Thorlabs",
        "perimax": "Perimax",
        "force_sensor": "Force",
    }

    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self._indicators: Dict[str, DeviceStatusIndicator] = {}
        self._previous_states: Dict[str, bool] = {}  # Track for change detection

        # Throttle state for live force reading (5 Hz = 200ms interval)
        self._force_last_update: float = 0.0
        self._force_throttle_s: float = 0.2
        self._force_device = None  # Set via set_force_device()

        self._setup_ui()

    def _setup_ui(self):
        layout = QHBoxLayout(self)
        layout.setContentsMargins(5, 0, 5, 0)
        layout.setSpacing(0)

        # Title
        title = QLabel("GOED")
        title.setStyleSheet("font-weight: bold; font-size: 14pt; padding: 5px;")
        layout.addWidget(title)

        # Separator
        sep1 = QLabel("|")
        sep1.setStyleSheet("color: #ccc; padding: 0 10px;")
        layout.addWidget(sep1)

        # Status label
        status_label = QLabel("Hardware Status:")
        status_label.setStyleSheet("font-weight: bold; padding: 5px;")
        layout.addWidget(status_label)

        # Device indicators
        device_ids = list(self.DEVICES.keys())
        for i, (device_id, display_name) in enumerate(self.DEVICES.items()):
            indicator = DeviceStatusIndicator(device_id, display_name)
            self._indicators[device_id] = indicator
            self._previous_states[device_id] = False
            layout.addWidget(indicator)

            # Add separator between devices (except last)
            if i < len(device_ids) - 1:
                sep = QLabel("|")
                sep.setStyleSheet("color: #ccc; padding: 0 5px;")
                layout.addWidget(sep)

        # Spacer
        spacer = QWidget()
        spacer.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        layout.addWidget(spacer)

        # Summary label
        self.summary_label = QLabel("Initializing...")
        self.summary_label.setStyleSheet("color: #666; padding: 5px;")
        layout.addWidget(self.summary_label)

    def update_status(self, status_data: Dict[str, dict]):
        """Update all device indicators from supervisor status data.

        Args:
            status_data: Dict mapping device_id to status dict with keys:
                - state: Wrapper state (stopped, ready, running, etc.)
                - hw_connected: Whether hardware is connected
                - hardware_ok: Whether hardware probe succeeded
                - hardware_error: Error message if probe failed
                - restart_count: Number of auto-restarts
                - circuit_state: Circuit breaker state (CLOSED, HALF_OPEN, OPEN)
                - circuit_failures: Consecutive failure count
        """
        logger.debug(f"HardwareStatusBar.update_status called with {len(status_data)} devices")

        connected_count = 0
        wrapper_ready_count = 0
        total_count = len(self._indicators)

        for device_id, indicator in self._indicators.items():
            device_status = status_data.get(device_id, {})

            state = device_status.get('state', 'stopped')
            hw_connected = device_status.get('hw_connected', False)
            hardware_ok = device_status.get('hardware_ok', True)
            hardware_error = device_status.get('hardware_error')
            restart_count = device_status.get('restart_count', 0)
            circuit_state = device_status.get('circuit_state', 'CLOSED')
            circuit_failures = device_status.get('circuit_failures', 0)

            # Update indicator
            indicator.update_status(
                state=state,
                hw_connected=hw_connected,
                hardware_ok=hardware_ok,
                hardware_error=hardware_error,
                restart_count=restart_count,
                circuit_state=circuit_state,
                circuit_failures=circuit_failures
            )

            # Count connections
            if state in ('ready', 'running'):
                wrapper_ready_count += 1
                if hw_connected and hardware_ok:
                    connected_count += 1

            # Emit signal on connection state change
            is_connected = hw_connected and hardware_ok and state in ('ready', 'running')
            if is_connected != self._previous_states.get(device_id, False):
                self._previous_states[device_id] = is_connected
                self.connection_changed.emit(device_id, is_connected)

        # Update summary
        self._update_summary(connected_count, wrapper_ready_count, total_count)

    def set_force_device(self, device):
        """Store reference to ForceWrapperDevice for reading offset."""
        self._force_device = device

    @Slot(float, float)
    def update_force_reading(self, t: float, force_n: float):
        """Update force sensor indicator with live reading, throttled to ~5 Hz.

        Connected to ForceWrapperDevice.signals.force_updated.
        Args:
            t: Elapsed time (unused here)
            force_n: Calibrated force in Newtons
        """
        now = time.monotonic()
        if (now - self._force_last_update) < self._force_throttle_s:
            return
        self._force_last_update = now

        indicator = self._indicators.get("force_sensor")
        if indicator is None:
            return

        # Display calibrated Newton value with warning colors
        warning_threshold = self._force_device.warning_threshold if self._force_device else 3.5
        abs_force = abs(force_n)
        arrow = "\u2193" if force_n >= 0 else "\u2191"  # ↓ compression, ↑ tension
        indicator.set_live_value(f"{arrow}{abs(force_n):.3f} N")

        # Override color: red if above warning threshold
        if abs_force >= warning_threshold:
            indicator.status_label.setStyleSheet(
                "color: #F44336; font-size: 9pt; min-width: 80px; font-weight: bold;"
            )

    def _update_summary(self, connected: int, ready: int, total: int):
        """Update the summary label."""
        if connected == total:
            summary = f"All {total} devices connected"
            style = "color: #4CAF50; font-weight: bold; padding: 5px;"
        elif connected > 0:
            summary = f"{connected}/{total} connected"
            style = "color: #FFC107; padding: 5px;"
        elif ready > 0:
            summary = f"{ready}/{total} ready"
            style = "color: #666; padding: 5px;"
        else:
            summary = "No devices"
            style = "color: #888; padding: 5px;"

        self.summary_label.setText(summary)
        self.summary_label.setStyleSheet(style)

    def get_summary_text(self) -> str:
        """Get current summary text for status bar."""
        return self.summary_label.text()

    def get_connection_status(self) -> Dict[str, bool]:
        """Get connection status for all devices."""
        return {
            device_id: indicator.is_connected()
            for device_id, indicator in self._indicators.items()
        }

    def is_device_connected(self, device_id: str) -> bool:
        """Check if a specific device is connected."""
        if device_id in self._indicators:
            return self._indicators[device_id].is_connected()
        return False


def create_hardware_status_toolbar(parent: Optional[QWidget] = None) -> tuple[QToolBar, HardwareStatusBar]:
    """Factory function to create a toolbar with hardware status bar.

    Returns:
        Tuple of (QToolBar, HardwareStatusBar) for adding to main window
    """
    toolbar = QToolBar("Hardware Status")
    toolbar.setMovable(False)

    status_bar = HardwareStatusBar()
    toolbar.addWidget(status_bar)

    return toolbar, status_bar
