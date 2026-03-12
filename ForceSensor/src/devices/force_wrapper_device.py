"""
I-7016 Force Sensor Device Implementation (Wrapper-based)

Wraps the DeviceSupervisor to provide process isolation for the DCON
force sensor module. Communicates via JSON IPC with scripts/force_bridge.py,
which handles serial communication.

Commands:
- ping, status, shutdown
- connect, disconnect
- read_force
- start_stream, stop_stream

Streaming:
- Bridge emits {"type":"data_point","data":{"t":...,"raw":...}} events
- DeviceSupervisor routes these to on_data_point callback
- This device re-emits via Qt signal: signals.force_updated(t, raw)
"""

import logging
from typing import Any, Dict, Optional

from PySide6.QtCore import QObject, Signal

from devices.base import DeviceInfo, DeviceState, CommandResult, CommandCallback
from devices.thread_safe_device import ThreadSafeDevice

logger = logging.getLogger(__name__)


class ForceWrapperSignals(QObject):
    """
    Qt signals for ForceWrapperDevice events.

    Created on the main thread to ensure proper signal delivery to GUI.
    """
    force_updated = Signal(float, float)   # (t, force_N) — calibrated Newtons
    state_changed = Signal(object)         # DeviceState
    error_occurred = Signal(str)           # Error message


class ForceWrapperDevice(ThreadSafeDevice):
    """
    I-7016 force sensor device using wrapper subprocess for process isolation.

    Communicates with scripts/force_bridge.py via JSON IPC, which talks
    to the I-7016 DCON module over RS232 serial.

    Supported commands:
    - "ping": Health check (DCON query)
    - "status": Get device status
    - "connect": Open serial port + verify DCON response
    - "disconnect": Stop stream + close serial
    - "read_force": Single-shot force reading
    - "start_stream": Begin continuous polling at Hz rate
    - "stop_stream": Stop continuous polling

    Usage:
        device = ForceWrapperDevice(config)
        device.connect_async(callback=on_connected)

        # After connected:
        device.execute_async("start_stream", {"hz": 20})
        # Force data arrives via device.signals.force_updated
    """

    CAPABILITIES = [
        "ping",
        "status",
        "connect",
        "disconnect",
        "read_force",
        "start_stream",
        "stop_stream",
    ]

    def __init__(self, config: Dict[str, Any], supervisor_service=None):
        """
        Initialize force sensor wrapper device.

        Args:
            config: Configuration dict from device_paths.yaml
            supervisor_service: Optional SupervisorService instance.
        """
        info = DeviceInfo(
            device_id="force_sensor",
            device_type="sensor",
            capabilities=self.CAPABILITIES,
            metadata={
                "wrapper": True,
                "process_isolation": True,
            }
        )
        super().__init__(info)

        self._config = config
        self._supervisor = None
        self._supervisor_service = supervisor_service

        if supervisor_service:
            self._attach_to_existing_supervisor()

        # Track which bridge PID we connected to (for restart detection)
        self._connected_bridge_pid: Optional[int] = None

        # Cached state
        self._streaming: bool = False
        self._last_raw: Optional[float] = None

        # Calibration: F(N) = slope * (raw - intercept)
        self._cal_slope: float = float(config.get("calibration_slope", -1.996))
        self._cal_intercept: float = float(config.get("calibration_intercept", 0.0360))

        # Safety thresholds (Newtons)
        self._warning_threshold: float = float(config.get("warning_threshold_N", 3.5))
        self._critical_threshold: float = float(config.get("critical_threshold_N", 4.5))

        # Zeroing offset in raw space (kept for potential future use, not exposed to GUI)
        self._offset: float = 0.0

        # Qt signals for UI updates
        self.signals = ForceWrapperSignals()

    @property
    def last_raw(self) -> Optional[float]:
        """Get last raw reading from sensor."""
        return self._last_raw

    @property
    def offset(self) -> float:
        """Get current zero offset (raw space)."""
        return self._offset

    @property
    def calibration_slope(self) -> float:
        """Get calibration slope."""
        return self._cal_slope

    @property
    def calibration_intercept(self) -> float:
        """Get calibration intercept (raw value at zero force)."""
        return self._cal_intercept

    @property
    def warning_threshold(self) -> float:
        """Get warning threshold in Newtons."""
        return self._warning_threshold

    @property
    def critical_threshold(self) -> float:
        """Get critical threshold in Newtons."""
        return self._critical_threshold

    def raw_to_newton(self, raw: float) -> float:
        """Convert raw sensor reading to force in Newtons.

        F(N) = slope * (raw - intercept)
        """
        return self._cal_slope * (raw - self._cal_intercept)

    @property
    def force_newton(self) -> Optional[float]:
        """Get calibrated force in Newtons, or None if no reading yet."""
        if self._last_raw is None:
            return None
        return self.raw_to_newton(self._last_raw)

    @property
    def is_streaming(self) -> bool:
        """Check if streaming is active."""
        return self._streaming

    def zero(self, value: Optional[float] = None):
        """Set zero offset.

        Args:
            value: Explicit offset value. If None, uses last_raw.
        """
        if value is not None:
            self._offset = value
        elif self._last_raw is not None:
            self._offset = self._last_raw
        logger.info(f"Force sensor: zero offset set to {self._offset}")

    def _attach_to_existing_supervisor(self):
        """Attach to an existing supervisor from SupervisorService."""
        if not self._supervisor_service:
            return

        try:
            with self._supervisor_service.devices_lock:
                supervisor = self._supervisor_service.devices.get("force_sensor")
                if supervisor:
                    logger.info(f"Force sensor: Found supervisor: state={supervisor.state.value}")
                    if supervisor.state.value == "ready":
                        self._supervisor = supervisor
                        self._set_state(DeviceState.READY)
                        self._wire_data_callback()
                    else:
                        logger.info(f"Force sensor: Supervisor not ready (state={supervisor.state.value})")
                else:
                    logger.info("Force sensor: No supervisor found in SupervisorService.devices")
        except Exception as e:
            logger.warning(f"Force sensor: Failed to attach to existing supervisor: {e}")

    def _wire_data_callback(self):
        """Wire the supervisor's on_data_point callback for streaming data."""
        if self._supervisor:
            self._supervisor.on_data_point = self._on_data_point

    def _on_data_point(self, response: Dict):
        """Handle streaming data_point events from the bridge.

        Called on the supervisor's stdout reader thread.
        Converts raw reading to calibrated Newtons before emitting.
        """
        data = response.get("data", {})
        t = data.get("t", 0.0)
        raw = data.get("raw", 0.0)

        self._last_raw = raw
        force_n = self.raw_to_newton(raw)
        self.signals.force_updated.emit(t, force_n)

    def _do_connect(self, timeout: float) -> CommandResult:
        """Start wrapper subprocess and connect to I-7016."""
        try:
            if self._supervisor is None:
                from supervisor.device_supervisor import DeviceSupervisor

                logger.info("Force sensor: Starting wrapper subprocess...")
                self._supervisor = DeviceSupervisor("force_sensor", self._config)
                self._supervisor.start()

                if self._supervisor.state.value != "ready":
                    error_msg = f"Wrapper started but unhealthy: {self._supervisor.state.value}"
                    stderr_tail = self._supervisor.get_stderr_tail(10)
                    if stderr_tail:
                        error_msg += f"\nStderr: {stderr_tail[-1]}"
                    logger.error(f"Force sensor: {error_msg}")
                    return CommandResult.error("WRAPPER_UNHEALTHY", error_msg)
            else:
                logger.info(f"Force sensor: Using existing supervisor (pid={self._supervisor.process.pid if self._supervisor.process else None})")

            # Wire streaming callback
            self._wire_data_callback()

            # Send connect command
            cmd = {"id": "connect-1", "action": "connect"}
            response = self._supervisor.send_command(cmd, timeout=timeout)

            if not response or not response.get("ok"):
                error = response.get("error", {}).get("message", "Unknown error") if response else "Timeout"
                logger.error(f"Force sensor: Connect failed: {error}")
                return CommandResult.error("CONNECT_FAILED", error)

            details = response.get("details", {})

            self._connected_bridge_pid = self._supervisor.process.pid if self._supervisor.process else None
            logger.info(f"Force sensor: Connected (port={details.get('port')}, bridge pid={self._connected_bridge_pid})")

            return CommandResult.ok(data={
                "state": self._supervisor.state.value,
                "pid": self._connected_bridge_pid,
                "port": details.get("port"),
                "address": details.get("address"),
                "test_value": details.get("test_value"),
                "mock": details.get("mock", False),
            })

        except ImportError as e:
            logger.error(f"Force sensor: DeviceSupervisor not available - {e}")
            return CommandResult.error("SUPERVISOR_MISSING", str(e))

        except Exception as e:
            logger.exception(f"Force sensor: Failed to connect - {e}")
            return CommandResult.error("CONNECT_FAILED", str(e))

    def _do_disconnect(self, timeout: float) -> CommandResult:
        """Disconnect from I-7016 and stop wrapper subprocess."""
        try:
            if self._supervisor is not None:
                # Send disconnect command (stops streaming, closes serial)
                try:
                    cmd = {"id": "disconnect-1", "action": "disconnect"}
                    self._supervisor.send_command(cmd, timeout=5.0)
                except Exception as e:
                    logger.warning(f"Force sensor: Disconnect command failed (stopping anyway): {e}")

                logger.info("Force sensor: Stopping wrapper subprocess...")
                self._supervisor.stop()
                self._supervisor = None

            self._streaming = False
            self._last_raw = None

            return CommandResult.ok()

        except Exception as e:
            logger.exception(f"Force sensor: Error during disconnect - {e}")
            return CommandResult.error("DISCONNECT_FAILED", str(e))

    def _do_execute(self, command: str, params: Dict[str, Any], timeout: float) -> CommandResult:
        """Execute a command on the force sensor wrapper."""
        if self._supervisor is None:
            return CommandResult.error("NOT_CONNECTED", "Wrapper not running")

        # Detect bridge restart — auto-reconnect and restore streaming
        current_pid = self._supervisor.process.pid if self._supervisor.process else None
        if self._connected_bridge_pid is not None and current_pid != self._connected_bridge_pid:
            logger.warning(f"Force sensor: Bridge restart detected (was pid={self._connected_bridge_pid}, now pid={current_pid})")
            was_streaming = self._streaming
            try:
                # Re-wire data callback to new supervisor instance
                self._wire_data_callback()

                # Re-establish serial connection
                cmd = {"id": "reconnect-1", "action": "connect"}
                response = self._supervisor.send_command(cmd, timeout=15.0)
                if response and response.get("ok"):
                    self._connected_bridge_pid = current_pid
                    logger.info(f"Force sensor: Auto-reconnect successful (new pid={current_pid})")

                    # Restore streaming if it was active before restart
                    if was_streaming:
                        stream_cmd = {"id": "reconnect-stream", "action": "start_stream", "params": {"hz": 20}}
                        stream_resp = self._supervisor.send_command(stream_cmd, timeout=5.0)
                        if stream_resp and stream_resp.get("ok"):
                            logger.info("Force sensor: Streaming restored after reconnect")
                        else:
                            logger.warning("Force sensor: Failed to restore streaming after reconnect")
                            self._streaming = False
                else:
                    error = response.get("error", {}).get("message", "Unknown") if response else "Timeout"
                    return CommandResult.error("RECONNECT_FAILED", f"Bridge restarted, reconnect failed: {error}")
            except Exception as e:
                return CommandResult.error("RECONNECT_FAILED", f"Bridge restarted, reconnect failed: {e}")

        if self._supervisor.state.value == "unhealthy":
            return CommandResult.error("UNHEALTHY", "Wrapper is unhealthy")

        try:
            if command == "ping":
                return self._cmd_ping(params, timeout)
            elif command == "status":
                return self._cmd_status(params, timeout)
            elif command == "read_force":
                return self._cmd_read_force(params, timeout)
            elif command == "start_stream":
                return self._cmd_start_stream(params, timeout)
            elif command == "stop_stream":
                return self._cmd_stop_stream(params, timeout)
            else:
                return CommandResult.error("UNKNOWN_COMMAND", f"Unknown command: {command}")

        except Exception as e:
            logger.exception(f"Force sensor: Command '{command}' failed - {e}")
            return CommandResult.error("COMMAND_FAILED", str(e))

    def _do_get_status(self) -> Dict[str, Any]:
        """Get force sensor-specific status."""
        if self._supervisor is None:
            return {"wrapper_state": "STOPPED"}

        status_dict = self._supervisor.get_status_dict()
        return {
            "wrapper_state": status_dict.get("state", "unknown"),
            "pid": status_dict.get("pid"),
            "uptime_s": status_dict.get("uptime_s"),
            "last_ping_ms": status_dict.get("last_ping_ms"),
            "restart_count": status_dict.get("restart_count"),
            "streaming": self._streaming,
            "last_raw": self._last_raw,
            "force_N": self.force_newton,
            "offset": self._offset,
        }

    # --- Command implementations ---

    def _cmd_ping(self, params: Dict[str, Any], timeout: float) -> CommandResult:
        cmd = {"id": "ping-1", "action": "ping"}
        response = self._supervisor.send_command(cmd, timeout=timeout)
        if response and response.get("ok"):
            return CommandResult.ok(data={"latency_ms": self._supervisor.last_ping_latency_ms})
        else:
            return CommandResult.error("PING_FAILED", "Ping timeout")

    def _cmd_status(self, params: Dict[str, Any], timeout: float) -> CommandResult:
        cmd = {"id": "status-1", "action": "status"}
        response = self._supervisor.send_command(cmd, timeout=timeout)
        if response and response.get("ok"):
            details = response.get("details", {})
            self._streaming = details.get("streaming", False)
            return CommandResult.ok(data=details)
        else:
            error = response.get("error", {}).get("message", "Unknown error") if response else "Timeout"
            return CommandResult.error("STATUS_FAILED", error)

    def _cmd_read_force(self, params: Dict[str, Any], timeout: float) -> CommandResult:
        cmd = {"id": "read_force-1", "action": "read_force"}
        response = self._supervisor.send_command(cmd, timeout=timeout)
        if response and response.get("ok"):
            details = response.get("details", {})
            if "raw" in details:
                self._last_raw = details["raw"]
            return CommandResult.ok(data=details)
        else:
            error = response.get("error", {}).get("message", "Unknown error") if response else "Timeout"
            return CommandResult.error("READ_FORCE_FAILED", error)

    def _cmd_start_stream(self, params: Dict[str, Any], timeout: float) -> CommandResult:
        cmd = {"id": "start_stream-1", "action": "start_stream", "params": params}
        response = self._supervisor.send_command(cmd, timeout=timeout)
        if response and response.get("ok"):
            self._streaming = True
            return CommandResult.ok(data=response.get("details", {}))
        else:
            error = response.get("error", {}).get("message", "Unknown error") if response else "Timeout"
            return CommandResult.error("START_STREAM_FAILED", error)

    def _cmd_stop_stream(self, params: Dict[str, Any], timeout: float) -> CommandResult:
        cmd = {"id": "stop_stream-1", "action": "stop_stream"}
        response = self._supervisor.send_command(cmd, timeout=timeout)
        if response and response.get("ok"):
            self._streaming = False
            return CommandResult.ok(data=response.get("details", {}))
        else:
            error = response.get("error", {}).get("message", "Unknown error") if response else "Timeout"
            return CommandResult.error("STOP_STREAM_FAILED", error)

    # --- Convenience methods ---

    def get_supervisor(self):
        """Access underlying DeviceSupervisor (for advanced use)."""
        return self._supervisor

    def get_stderr_tail(self, lines: int = 20) -> list:
        """Get recent stderr output from wrapper (for debugging)."""
        if self._supervisor:
            return self._supervisor.get_stderr_tail(lines)
        return []
