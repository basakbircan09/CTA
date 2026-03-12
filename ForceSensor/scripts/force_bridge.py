#!/usr/bin/env python3
"""
GOED Bridge for ICP DAS I-7016 Force Sensor (DCON Protocol)

Communicates with I-7016 analog input module via RS232 serial
(9600 baud, 8N1). Translates JSON IPC on stdin/stdout to DCON
commands for process isolation.

DCON protocol: send "#AA\\r" (AA = hex address), receive ">+NNNNN.NNNNN\\r"

Conforms to: GOED/docs/schemas/WRAPPER_IO.md v0.3.0

Commands:
- ping, status, shutdown
- connect, disconnect
- read_force
- start_stream, stop_stream
"""

import sys
import os
import json
import argparse
import logging
import time
import re
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Optional

VERSION = "0.1.0"
DEVICE_NAME = "force_sensor"

# Serial defaults matching DCON / I-7016
DEFAULT_BAUD = 9600
DEFAULT_ADDRESS = "02"
DEFAULT_TIMEOUT = 0.5       # seconds for serial read timeout
DEFAULT_STREAM_HZ = 20      # polling rate for streaming

# Regex for DCON response: ">+NNNNN.NNNNN" or ">-NNNNN.NNNNN"
DCON_RESP_RE = re.compile(r"^>\s*([+-]?\d+(?:\.\d+)?)\s*$")
# Fallback: extract first float from any response
FLOAT_RE = re.compile(r"[-+]?\d+(?:\.\d+)?")


class ForceBridge:
    """
    GOED Bridge for I-7016 force sensor via DCON serial protocol.

    Runs in subprocess for process isolation from other USB devices.
    """

    def __init__(self, device_name: str, log_dir: str, mock_mode: bool = True,
                 port: str = "COM8", baud: int = DEFAULT_BAUD,
                 address: str = DEFAULT_ADDRESS):
        self.device_name = device_name
        self.mock_mode = mock_mode
        self.start_time = time.time()
        self.port = port
        self.baud = baud
        self.address = address

        # Setup logging to file only (NOT stdout - stdout is JSON only)
        log_path = Path(log_dir) / "force_bridge.log"
        log_path.parent.mkdir(parents=True, exist_ok=True)

        logging.basicConfig(
            level=logging.DEBUG if mock_mode else logging.INFO,
            format='%(asctime)s [%(levelname)s] [%(name)s] %(message)s',
            handlers=[
                logging.FileHandler(log_path),
            ],
            force=True
        )
        self.logger = logging.getLogger(f"goed.{device_name}")
        self.logger.info(f"Wrapper started: device={device_name} mode={'mock' if mock_mode else 'hardware'}")

        # Serial connection
        self._serial = None
        self.connected = False

        # Streaming state
        self._stream_thread: Optional[threading.Thread] = None
        self._stream_running = False
        self._stream_hz = DEFAULT_STREAM_HZ
        self._stdout_lock = threading.Lock()
        self._serial_lock = threading.Lock()  # Protect serial access from concurrent stream + command

        # Mock state
        self._mock_t0 = time.perf_counter()

    # -------------------------------------------------------------------------
    # DCON Serial Communication
    # -------------------------------------------------------------------------

    def _serial_open(self):
        """Open serial connection to I-7016 DCON module."""
        import serial

        self.logger.info(f"Opening serial port {self.port} at {self.baud} baud")
        self._serial = serial.Serial(
            port=self.port,
            baudrate=self.baud,
            bytesize=serial.EIGHTBITS,
            parity=serial.PARITY_NONE,
            stopbits=serial.STOPBITS_ONE,
            timeout=DEFAULT_TIMEOUT,
            write_timeout=DEFAULT_TIMEOUT,
            rtscts=False,
            dsrdtr=False,
        )
        self.logger.info(f"Serial port {self.port} opened")

    def _serial_close(self):
        """Close serial connection."""
        if self._serial and self._serial.is_open:
            self._serial.close()
            self.logger.info("Serial port closed")
        self._serial = None

    def _dcon_query(self) -> float:
        """Send DCON query and parse float response.

        Sends "#AA\\r" and expects ">+NNNNN.NNNNN" back.
        Thread-safe: acquires _serial_lock to prevent concurrent access
        from the streaming thread and the command handler.

        Returns:
            Parsed float value from the sensor.

        Raises:
            ValueError: If response cannot be parsed
            RuntimeError: If serial port not open
        """
        if not self._serial or not self._serial.is_open:
            raise RuntimeError("Serial port not open")

        with self._serial_lock:
            cmd = f"#{self.address}\r".encode("ascii")

            self._serial.reset_input_buffer()
            self._serial.write(cmd)
            self._serial.flush()

            # Read response — DCON devices respond quickly
            raw = self._serial.read(64).decode("ascii", errors="replace").strip()

        if not raw:
            raise ValueError("No response from sensor")

        # Try strict DCON format first
        m = DCON_RESP_RE.match(raw)
        if m:
            return float(m.group(1))

        # Fallback: extract first float
        m = FLOAT_RE.search(raw)
        if m:
            self.logger.debug(f"Used fallback float parse for: {raw!r}")
            return float(m.group(0))

        raise ValueError(f"Cannot parse DCON response: {raw!r}")

    # -------------------------------------------------------------------------
    # Response Builder (WRAPPER_IO.md compliant)
    # -------------------------------------------------------------------------

    def get_timestamp(self) -> str:
        """Return ISO 8601 timestamp with milliseconds in UTC."""
        return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "Z"

    def get_uptime(self) -> int:
        """Return uptime in seconds since wrapper started."""
        return int(time.time() - self.start_time)

    def build_response(self, cmd_id: str, action: str, ok: bool = True,
                       details: Optional[Dict] = None, error: Optional[Dict] = None) -> Dict:
        """Build standard response according to WRAPPER_IO.md spec."""
        response = {
            "id": cmd_id,
            "ok": ok,
            "device": self.device_name,
            "ts": self.get_timestamp(),
            "version": VERSION
        }

        if ok:
            response["action"] = action
            if details:
                response["details"] = details
        else:
            if action:
                response["action"] = action
            if error:
                response["error"] = error

        return response

    def _write_stdout(self, data: Dict):
        """Thread-safe write to stdout."""
        with self._stdout_lock:
            print(json.dumps(data), flush=True)

    # -------------------------------------------------------------------------
    # Streaming
    # -------------------------------------------------------------------------

    def _stream_loop(self):
        """Background thread: poll sensor at configured Hz, emit data_point events."""
        period = 1.0 / max(1, self._stream_hz)
        t0 = time.perf_counter()
        self.logger.info(f"Streaming started at {self._stream_hz} Hz")

        while self._stream_running:
            try:
                if self.mock_mode:
                    t = time.perf_counter() - self._mock_t0
                    # Simulate slowly drifting force with noise
                    import math
                    raw = 0.5 + 0.1 * math.sin(t * 0.3) + 0.01 * math.sin(t * 7.0)
                else:
                    raw = self._dcon_query()

                t = time.perf_counter() - t0

                # Emit as data_point event (same format as Gamry streaming)
                event = {
                    "type": "data_point",
                    "device": self.device_name,
                    "data": {
                        "t": round(t, 4),
                        "raw": round(raw, 6),
                    }
                }
                self._write_stdout(event)

            except Exception as e:
                self.logger.warning(f"Stream read error: {e}")
                # Don't flood on repeated errors
                time.sleep(0.5)
                continue

            time.sleep(period)

        self.logger.info("Streaming stopped")

    # -------------------------------------------------------------------------
    # Action Handlers
    # -------------------------------------------------------------------------

    def handle_ping(self, cmd_id: str, params: Dict) -> Dict:
        """Handle ping command.

        When streaming is active, skip the hardware query — the streaming
        thread already proves liveness. This avoids serial contention that
        could cause ping timeouts and spurious auto-restarts.
        """
        self.logger.debug(f"[{cmd_id}] Processing ping (streaming={self._stream_running})")

        if self.mock_mode:
            return self.build_response(cmd_id, "ping", details={"mock": True})

        if not self.connected:
            return self.build_response(cmd_id, "ping", details={
                "connected": False,
                "hardware_ok": None
            })

        # When streaming, the stream thread is continuously querying the sensor.
        # Skip the redundant hardware query to avoid serial lock contention
        # and the resulting ping timeout → unhealthy → auto-restart cycle.
        if self._stream_running:
            return self.build_response(cmd_id, "ping", details={
                "connected": True,
                "hardware_ok": True,
                "streaming": True,
            })

        try:
            t_start = time.perf_counter()
            self._dcon_query()
            latency_ms = (time.perf_counter() - t_start) * 1000
            return self.build_response(cmd_id, "ping", details={
                "connected": True,
                "hardware_ok": True,
                "latency_ms": round(latency_ms, 1),
            })
        except Exception as e:
            self.logger.warning(f"[{cmd_id}] Ping failed: {e}")
            return self.build_response(
                cmd_id, "ping", ok=False,
                error={
                    "code": "HARDWARE_ERROR",
                    "message": f"Sensor not responding: {str(e)}"
                }
            )

    def handle_status(self, cmd_id: str, params: Dict) -> Dict:
        """Handle status command."""
        self.logger.info(f"[{cmd_id}] Processing status")

        details = {
            "state": "idle" if self.connected else "disconnected",
            "uptime_s": self.get_uptime(),
            "connected": self.connected,
            "mock": self.mock_mode,
            "streaming": self._stream_running,
            "stream_hz": self._stream_hz if self._stream_running else None,
            "port": self.port,
            "address": self.address,
        }

        return self.build_response(cmd_id, "status", details=details)

    def handle_shutdown(self, cmd_id: str, params: Dict) -> Dict:
        """Handle shutdown command."""
        self.logger.info(f"[{cmd_id}] Processing shutdown")

        # Stop streaming if active
        self._stop_streaming()

        if self.connected:
            try:
                self._serial_close()
                self.connected = False
            except Exception as e:
                self.logger.error(f"Error during shutdown: {e}")

        return self.build_response(cmd_id, "shutdown")

    def handle_connect(self, cmd_id: str, params: Dict) -> Dict:
        """Handle connect command — open serial port and verify communication."""
        self.logger.info(f"[{cmd_id}] Processing connect")

        if self.mock_mode:
            self.connected = True
            self._mock_t0 = time.perf_counter()
            return self.build_response(cmd_id, "connect", details={
                "mock": True,
                "port": self.port,
                "address": self.address,
            })

        if self.connected:
            return self.build_response(cmd_id, "connect", details={"already_connected": True})

        try:
            self._serial_open()

            # Verify communication with a test read
            value = self._dcon_query()
            self.connected = True
            self.logger.info(f"I-7016 connected on {self.port} addr={self.address}, test read={value}")

            return self.build_response(cmd_id, "connect", details={
                "port": self.port,
                "address": self.address,
                "test_value": round(value, 6),
            })

        except Exception as e:
            self.logger.exception(f"[{cmd_id}] Connect failed: {e}")
            self._serial_close()
            return self.build_response(
                cmd_id, "connect", ok=False,
                error={
                    "code": "HARDWARE_ERROR",
                    "message": f"Failed to connect: {str(e)}"
                }
            )

    def handle_disconnect(self, cmd_id: str, params: Dict) -> Dict:
        """Handle disconnect command — stop streaming and close serial."""
        self.logger.info(f"[{cmd_id}] Processing disconnect")

        if self.mock_mode:
            self._stop_streaming()
            self.connected = False
            return self.build_response(cmd_id, "disconnect", details={"mock": True})

        if not self.connected:
            return self.build_response(cmd_id, "disconnect", details={"already_disconnected": True})

        try:
            self._stop_streaming()
            self._serial_close()
            self.connected = False
            return self.build_response(cmd_id, "disconnect")
        except Exception as e:
            self.logger.exception(f"[{cmd_id}] Disconnect failed: {e}")
            return self.build_response(
                cmd_id, "disconnect", ok=False,
                error={
                    "code": "HARDWARE_ERROR",
                    "message": f"Failed to disconnect: {str(e)}"
                }
            )

    def handle_read_force(self, cmd_id: str, params: Dict) -> Dict:
        """Handle read_force — single-shot force reading."""
        self.logger.debug(f"[{cmd_id}] Processing read_force")

        if self.mock_mode:
            import math
            t = time.perf_counter() - self._mock_t0
            raw = 0.5 + 0.1 * math.sin(t * 0.3) + 0.01 * math.sin(t * 7.0)
            return self.build_response(cmd_id, "read_force", details={
                "mock": True,
                "raw": round(raw, 6),
                "timestamp": self.get_timestamp(),
            })

        if not self.connected:
            return self.build_response(
                cmd_id, "read_force", ok=False,
                error={
                    "code": "INVALID_STATE",
                    "message": "Not connected — call connect first"
                }
            )

        try:
            raw = self._dcon_query()
            return self.build_response(cmd_id, "read_force", details={
                "raw": round(raw, 6),
                "timestamp": self.get_timestamp(),
            })
        except Exception as e:
            self.logger.exception(f"[{cmd_id}] read_force failed: {e}")
            return self.build_response(
                cmd_id, "read_force", ok=False,
                error={
                    "code": "HARDWARE_ERROR",
                    "message": f"Failed to read: {str(e)}"
                }
            )

    def handle_start_stream(self, cmd_id: str, params: Dict) -> Dict:
        """Handle start_stream — begin continuous polling at configured Hz."""
        hz = params.get("hz", DEFAULT_STREAM_HZ)
        self.logger.info(f"[{cmd_id}] Processing start_stream (hz={hz})")

        if self._stream_running:
            return self.build_response(cmd_id, "start_stream", details={
                "already_streaming": True,
                "hz": self._stream_hz,
            })

        if not self.mock_mode and not self.connected:
            return self.build_response(
                cmd_id, "start_stream", ok=False,
                error={
                    "code": "INVALID_STATE",
                    "message": "Not connected — call connect first"
                }
            )

        try:
            hz = max(1, min(200, int(hz)))
        except (ValueError, TypeError):
            hz = DEFAULT_STREAM_HZ

        self._stream_hz = hz
        self._stream_running = True
        self._stream_thread = threading.Thread(
            target=self._stream_loop, daemon=True, name="force_stream"
        )
        self._stream_thread.start()

        return self.build_response(cmd_id, "start_stream", details={"hz": hz})

    def handle_stop_stream(self, cmd_id: str, params: Dict) -> Dict:
        """Handle stop_stream — stop continuous polling."""
        self.logger.info(f"[{cmd_id}] Processing stop_stream")

        if not self._stream_running:
            return self.build_response(cmd_id, "stop_stream", details={"already_stopped": True})

        self._stop_streaming()
        return self.build_response(cmd_id, "stop_stream")

    # -------------------------------------------------------------------------
    # Helpers
    # -------------------------------------------------------------------------

    def _stop_streaming(self):
        """Stop the streaming thread if running."""
        if self._stream_running:
            self._stream_running = False
            if self._stream_thread and self._stream_thread.is_alive():
                self._stream_thread.join(timeout=2.0)
            self._stream_thread = None

    # -------------------------------------------------------------------------
    # Command Dispatch
    # -------------------------------------------------------------------------

    def handle_command(self, line: str) -> Dict:
        """Parse and dispatch a single command line."""
        try:
            cmd = json.loads(line)
        except json.JSONDecodeError as e:
            self.logger.error(f"Invalid JSON: {e}")
            return self.build_response(
                "unknown", None, ok=False,
                error={
                    "code": "INVALID_JSON",
                    "message": f"Failed to parse JSON: {str(e)}",
                    "details": {"received": line.strip()[:100]}
                }
            )

        cmd_id = cmd.get("id")
        if not cmd_id:
            return self.build_response(
                "unknown", cmd.get("action"), ok=False,
                error={"code": "MISSING_FIELD", "message": "Missing required field: id"}
            )

        action = cmd.get("action")
        if not action:
            return self.build_response(
                cmd_id, None, ok=False,
                error={"code": "MISSING_FIELD", "message": "Missing required field: action"}
            )

        params = cmd.get("params", {})

        handlers = {
            "ping": self.handle_ping,
            "status": self.handle_status,
            "shutdown": self.handle_shutdown,
            "connect": self.handle_connect,
            "disconnect": self.handle_disconnect,
            "read_force": self.handle_read_force,
            "start_stream": self.handle_start_stream,
            "stop_stream": self.handle_stop_stream,
        }

        handler = handlers.get(action)
        if handler:
            return handler(cmd_id, params)
        else:
            self.logger.warning(f"[{cmd_id}] Unknown action: {action}")
            return self.build_response(
                cmd_id, action, ok=False,
                error={
                    "code": "UNKNOWN_ACTION",
                    "message": f"Unknown action: {action}",
                    "details": {"supported": list(handlers.keys())}
                }
            )

    def run(self, once: bool = False):
        """Main loop: read stdin, process commands, write stdout."""
        self.logger.info("Entering main loop")

        try:
            for line in sys.stdin:
                line = line.strip()
                if not line:
                    continue

                try:
                    response = self.handle_command(line)
                    self._write_stdout(response)

                    if response.get("ok") and response.get("action") == "shutdown":
                        self.logger.info("Shutdown requested, exiting")
                        sys.exit(0)

                    if once:
                        self.logger.info("--once flag set, exiting after first command")
                        sys.exit(0)

                except Exception as e:
                    self.logger.exception(f"Internal error processing command: {e}")
                    error_response = self.build_response(
                        "unknown", None, ok=False,
                        error={
                            "code": "INTERNAL_ERROR",
                            "message": f"Unhandled exception: {str(e)}"
                        }
                    )
                    self._write_stdout(error_response)

                    if once:
                        sys.exit(1)

        except KeyboardInterrupt:
            self.logger.info("Interrupted by user")
            self._stop_streaming()
            sys.exit(0)
        except Exception as e:
            self.logger.exception(f"Fatal error in main loop: {e}")
            self._stop_streaming()
            sys.exit(1)


def main():
    parser = argparse.ArgumentParser(description="GOED Bridge for I-7016 Force Sensor (DCON)")
    parser.add_argument("--mock", action="store_true", default=False,
                        help="Run in mock mode (no hardware calls)")
    parser.add_argument("--log-dir", type=str, default="logs",
                        help="Directory for log files (default: logs/)")
    parser.add_argument("--once", action="store_true",
                        help="Process one command then exit (for testing)")
    parser.add_argument("--device", type=str, default=DEVICE_NAME,
                        help=f"Override device name (default: {DEVICE_NAME})")
    parser.add_argument("--port", type=str, default="COM8",
                        help="Serial port (default: COM8)")
    parser.add_argument("--baud", type=int, default=DEFAULT_BAUD,
                        help=f"Baud rate (default: {DEFAULT_BAUD})")
    parser.add_argument("--address", type=str, default=DEFAULT_ADDRESS,
                        help=f"DCON device address (default: {DEFAULT_ADDRESS})")

    args = parser.parse_args()

    print(f"[GOED] Force sensor wrapper started: device={args.device} mode={'mock' if args.mock else 'hardware'}",
          file=sys.stderr, flush=True)

    bridge = ForceBridge(
        device_name=args.device,
        log_dir=args.log_dir,
        mock_mode=args.mock,
        port=args.port,
        baud=args.baud,
        address=args.address,
    )
    bridge.run(once=args.once)


if __name__ == "__main__":
    main()
