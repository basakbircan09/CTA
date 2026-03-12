# Force Sensor (I-7016 DCON) Integration Plan

**Date:** 2026-03-10
**Status:** Implemented (1WE GUI, mock validated)
**Device:** ICP DAS I-7016 analog input module (DCON protocol over RS232/RS485)
**Branch:** `2we`

---

## 1. Device Profile

| Property | Value |
|----------|-------|
| **Module** | ICP DAS I-7016 (or similar DCON device) |
| **Protocol** | DCON ASCII over RS232/RS485 (9600 8N1) |
| **Command format** | `#AA\r` where AA = 2-digit hex address (default `02`) |
| **Response format** | `>+NNNNN.NNNNN\r` (leading `>`, sign, float) |
| **Polling rate** | Up to ~20 Hz (50ms per query round-trip) |
| **Data** | Single analog channel → raw float (voltage/mV) |
| **Calibration** | Offset zeroing (averaged baseline), optional scale factor (N per raw unit) |
| **COM port** | Hardcoded COM8 in reference scripts; GOED should use config |
| **Use case** | Real-time contact force monitoring during scanning flow cell approach to substrate |

---

## 2. Reference Script Analysis

### `forcesensor.py` — Low-level driver

- `open_port(port, baud)` → `serial.Serial` with DCON defaults (9600 8N1, 500ms timeout)
- `dcon_query(ser, cmd, line_ending)` → send ASCII command, read until 250ms silence
- `parse_first_float(s)` → regex extract first number from response
- Single-shot: send `#02`, parse float

### `FS_realtime.py` — Real-time GUI

- `ForceWorker(QThread)` — polling loop at configurable Hz:
  - Sends `#02\r`, reads 64 bytes, parses with regex `^>\s*([+-]?\d+(?:\.\d+)?)\s*$`
  - Emits `new_sample(t, raw)` signal at each cycle
  - Emits `status(str)` for connection state changes
- `ForceMonitor(QWidget)` — standalone PySide6 app:
  - PyQtGraph live plot (deque of 2000 samples)
  - Offset zeroing (average last N samples)
  - Optional scale factor (N per raw unit)
  - Start/Stop/Zero buttons, port/baud/Hz selectors

### Key observations

1. **DCON protocol is trivially simple** — single command (`#AA`), single float response
2. **No persistent connection state** — each query is independent; serial port open = connected
3. **No hardware mode switching** (unlike Perimax SOM/ACK) — just poll
4. **Response parsing uses two different regexes** between the two files — GOED bridge should unify to the more specific `^>\s*([+-]?\d+(?:\.\d+)?)\s*$`
5. **Zeroing/calibration is application-level** — bridge returns raw values; GOED-side applies offset/scale
6. **Streaming is the primary use case** — this device is most useful as continuous telemetry, not request/response

---

## 3. GOED Integration Architecture

Following the established 4-layer pattern (Bridge → Device → Panel → Config):

```
┌─────────────────────────────────────────────────────────┐
│                    Main Process (GOED GUI)                │
│  ForceControlPanel ← DeviceRegistry.get("force_sensor")  │
│  Live plot widget + Zero button + value display           │
└──────────────────────┬──────────────────────────────────┘
                       │ JSON IPC (stdin/stdout)
                       ▼
┌─────────────────────────────────────────────────────────┐
│           scripts/force_bridge.py (subprocess)            │
│  pyserial → DCON I-7016 over RS232                        │
│  Commands: ping, status, connect, disconnect, shutdown    │
│            read_force, start_stream, stop_stream, zero    │
│  Streaming: {"event":"force_data", "payload":{t, raw}}    │
└─────────────────────────────────────────────────────────┘
```

---

## 4. Files to Create/Modify

### New files (4)

| File | Purpose | Template |
|------|---------|----------|
| `scripts/force_bridge.py` | Wrapper subprocess for DCON serial communication | `scripts/perimax_bridge.py` |
| `src/devices/force_wrapper_device.py` | Device class with streaming support | `src/devices/perimax_wrapper_device.py` |
| `src/gui/panels/force_control_panel.py` | GUI panel with live force plot | `src/gui/panels/perimax_control_panel.py` |
| `docs/force_sensor/FORCE_SENSOR_INTEGRATION_PLAN_2026-03-10.md` | This document |

### Modified files (5)

| File | Change |
|------|--------|
| `config/device_paths.yaml` | Add `force_sensor` device entry |
| `src/devices/__init__.py` | Export `ForceWrapperDevice` |
| `src/entrypoints/goed_gui_v3.py` | Register force_sensor device + add tab |
| `src/entrypoints/goed_gui_2we_v3_scaffold.py` | Register force_sensor device + add tab |
| `docs/schemas/WRAPPER_IO.md` | Document force_sensor commands (optional, can be deferred) |

---

## 5. Detailed Design per Layer

### Layer 1: `scripts/force_bridge.py`

**Structure:** Copy `perimax_bridge.py` skeleton. Replace serial protocol with DCON.

**Commands:**

| Action | Params | Response | Notes |
|--------|--------|----------|-------|
| `ping` | — | `{ok, details: {connected, latency_ms}}` | Send `#02`, verify response |
| `status` | — | `{ok, details: {state, connected, mock, uptime_s, streaming}}` | |
| `connect` | `{port?, baud?, address?}` | `{ok, details: {port, address}}` | Open serial, verify with test read |
| `disconnect` | — | `{ok}` | Stop stream, close serial |
| `shutdown` | — | `{ok}` | Disconnect + exit |
| `read_force` | — | `{ok, details: {raw, timestamp}}` | Single-shot DCON query |
| `start_stream` | `{hz?: 20}` | `{ok, details: {hz}}` | Start background polling thread |
| `stop_stream` | — | `{ok}` | Stop polling thread |

**Streaming events** (unsolicited, emitted from polling thread):
```json
{"event": "force_data", "device": "force_sensor", "payload": {"t": 1.234, "raw": 0.00567}}
```

This matches the WRAPPER_IO.md event pattern already used by Gamry for streaming data points.

**Serial implementation notes:**
- Reuse the DCON query logic from `forcesensor.py` (`dcon_query` + `parse_first_float`)
- Streaming thread polls at configured Hz, writes events to stdout
- Thread-safe: streaming thread only writes events; main thread handles commands
- Mock mode: generate sinusoidal fake force data

**Auto-detection:** The I-7016 doesn't use FTDI — it's typically on a dedicated COM port. Config should specify the port explicitly. Optional: scan COM ports and send `#02` to identify.

### Layer 2: `src/devices/force_wrapper_device.py`

**Structure:** Copy `perimax_wrapper_device.py`. Key differences:

- **Device ID:** `"force_sensor"`
- **Device type:** `"sensor"`
- **Capabilities:** `["ping", "status", "connect", "disconnect", "read_force", "start_stream", "stop_stream"]`
- **Streaming support:** Handle `force_data` events from DeviceSupervisor's event callback
- **Cached state:** `_last_raw`, `_offset`, `_scale`, `_streaming`
- **Qt signals:**
  ```python
  class ForceWrapperSignals(QObject):
      force_updated = Signal(float, float)  # (t, raw_value)
      state_changed = Signal(object)        # DeviceState
      error_occurred = Signal(str)
  ```
- **Zero method:** `zero()` — averages recent readings and stores offset (application-side, not sent to bridge)
- **Calibrated value:** `force_n` property that applies `(raw - offset) * scale`

**Event handling:** DeviceSupervisor already has `on_event` callback for unsolicited messages. Wire `force_data` events to `signals.force_updated.emit(t, raw)`.

### Layer 3: `src/gui/panels/force_control_panel.py`

**Layout:**

```
┌─ Connection ─────────────────────────────┐
│ [Connect]  [Disconnect]   Status: Idle   │
└──────────────────────────────────────────┘
┌─ Live Force ─────────────────────────────┐
│                                          │
│   ┌── Big value display ──────────────┐  │
│   │    +0.234 N  (or +0.00567 raw)    │  │
│   └───────────────────────────────────┘  │
│   raw: +0.00567  offset: +0.00123        │
│   scale: 42.0 N/unit                     │
│                                          │
│   [Zero]  [Start Stream]  [Stop Stream]  │
│                                          │
│   ┌── PyQtGraph plot ────────────────┐   │
│   │  Force vs Time (rolling 100s)    │   │
│   └──────────────────────────────────┘   │
│                                          │
│   Hz: [20]   Address: [02]               │
└──────────────────────────────────────────┘
```

**Key UI elements:**
- Big force value label (48px font, like `FS_realtime.py`)
- Sub-label with raw / offset / scale
- PyQtGraph PlotWidget with rolling time window (reuse deque pattern from `FS_realtime.py`)
- Zero button (averages last ~0.5s of samples)
- Start/Stop stream buttons
- Configurable Hz and DCON address

**Thread safety:** Use `_device_result` signal pattern (same as Perimax panel) for command results. Streaming data arrives via `device.signals.force_updated` which is Qt signal — already thread-safe for GUI updates.

### Layer 4: `config/device_paths.yaml`

```yaml
  force_sensor:
    repo: 'C:\Users\AKL\Documents\GitHub\GOED'
    python: 'python'
    wrapper: 'scripts/force_bridge.py'
    mode: 'hardware'  # or 'mock' for testing
    startup_timeout_s: 10
    args:
      - '--port'
      - 'COM8'
      - '--address'
      - '02'
    env:
      PYTHONPATH: 'C:\Users\AKL\Documents\GitHub\GOED\src'
```

---

## 6. Streaming Architecture Detail

The force sensor is unique among GOED devices: it's the first **continuous telemetry sensor** (Gamry streams during technique execution, but force sensor streams independently).

**Event flow:**
```
force_bridge.py (subprocess)
  └─ polling thread: serial query every 50ms
       └─ stdout: {"event":"force_data","device":"force_sensor","payload":{"t":1.23,"raw":0.005}}

DeviceSupervisor._read_stdout()
  └─ detects "event" key → calls on_event callback

ForceWrapperDevice
  └─ event handler → signals.force_updated.emit(t, raw)

ForceControlPanel
  └─ force_updated signal → on_force_sample() → update plot + labels
```

DeviceSupervisor already handles this: in `_read_stdout()`, responses with `"event"` key are routed to `self.on_event(parsed_json)` instead of the pending command queue. This is the same path Gamry uses for streaming data points.

---

## 7. Differences from Perimax Integration

| Aspect | Perimax | Force Sensor |
|--------|---------|--------------|
| Protocol | SMC01 custom commands + ACK mode | DCON standard (`#AA\r`) |
| Mode switching | SOM 1 0 (USB mode), ACK 1 | None needed |
| Primary use | Command/response (set speed, stop) | Continuous streaming (force telemetry) |
| GUI plot | No plot | Live force vs time (PyQtGraph) |
| Calibration | Not applicable | Offset zeroing + scale factor |
| Auto-detect | FTDI VID scan | Explicit COM port (no standard VID) |
| Complexity | Medium (multi-command protocol) | Low (single query command) |

---

## 8. Implementation Order

| Step | Description | Scope |
|------|-------------|-------|
| **1** | Create `scripts/force_bridge.py` with mock mode + DCON serial | S-M |
| **2** | Add `force_sensor` to `config/device_paths.yaml` | XS |
| **3** | Create `src/devices/force_wrapper_device.py` | S |
| **4** | Export in `src/devices/__init__.py` | XS |
| **5** | Create `src/gui/panels/force_control_panel.py` with live plot | M |
| **6** | Wire into `goed_gui_v3.py` and `goed_gui_2we_v3_scaffold.py` | S |
| **7** | Test mock mode end-to-end | S |
| **8** | Hardware validation | Hardware |

**Total estimated scope:** Medium — comparable to Perimax integration.

---

## 9. Open Questions

1. **COM port stability:** Is COM8 always the force sensor, or does it change? Should we add address-based auto-detection (send `#02` to each COM port)?
2. **Scale factor:** What is the N-per-raw-unit calibration? Is this per-sensor or universal? Should it be in config?
3. **Integration with PI Z-approach:** The primary use case is monitoring contact force during flow cell approach. Should the force value be available to the sequence engine (e.g., "move Z until force > threshold")?
4. **Data logging:** Should force telemetry be logged to CSV during sequences (like Gamry data points)?
5. **2WE relevance:** Is the force sensor used in both 1WE and 2WE workflows, or only one?
