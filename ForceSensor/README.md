# GOED – General Orchestrator for Electrochemistry Devices

**Branch:** `2we` — Primary development branch. All active development continues here.

GOED is the coordination layer that supervises five scientific-control codebases via process-isolated wrapper/subprocess architecture:

| Device | SDK | Wrapper | Purpose |
|--------|-----|---------|---------|
| **Gamry** | ToolkitPy (Python 3.7-32) | `scripts/goed_bridge.py` (external repo) | Potentiostat — CV, LSV, CA, CP, OCV, EIS |
| **PI XYZ** | pipython (Python 3.13) | `scripts/pi_bridge.py` | 3-axis stage — home, jog, move, park, waypoint sequences |
| **Thorlabs** | pylablib (Python 3.13) | `scripts/thorlabs_bridge.py` | CS165CU camera — live view, snapshots, exposure/gain |
| **Perimax** | pyserial (Python 3.13) | `scripts/perimax_bridge.py` | SMC01 peristaltic pump — speed, direction, start/stop |
| **Force Sensor** | pyserial (Python 3.13) | `scripts/force_bridge.py` | I-7016 DCON — contact force monitoring, real-time streaming |

Each device runs in an **isolated subprocess** communicating via JSON IPC (stdin/stdout). GOED never imports device SDKs directly — this is critical due to USB/DLL conflicts between SDKs.

## Documentation Map

| Document | Purpose |
|----------|---------|
| [`docs/README_DAILY.md`](docs/README_DAILY.md) | Daily init checklist, current state, workflow |
| [`docs/PROJECT_OVERVIEW.md`](docs/PROJECT_OVERVIEW.md) | Mission, goals, success criteria |
| [`docs/setup/DEVICE_PORTFOLIO.md`](docs/setup/DEVICE_PORTFOLIO.md) | Canonical reference for device repos |
| [`docs/architecture/ARCHITECTURE.md`](docs/architecture/ARCHITECTURE.md) | Process model, IPC contracts, GUI layering |
| [`docs/guides/DEVICE_INTEGRATION_GUIDE.md`](docs/guides/DEVICE_INTEGRATION_GUIDE.md) | Device abstraction layer, migration guide |
| [`docs/guides/GAMRY_HARDWARE_SOP.md`](docs/guides/GAMRY_HARDWARE_SOP.md) | Safety protocols for hardware sessions |
| [`docs/ROADMAP.md`](docs/ROADMAP.md) | Timeline with phases, readiness gates, deliverables |
| [`docs/setup/NEW_PC_SETUP.md`](docs/setup/NEW_PC_SETUP.md) | New-PC installation guide (Python + vendor suites) |
| [`docs/setup/SETUP_GUIDE.md`](docs/setup/SETUP_GUIDE.md) | Compact setup checklist |
| [`docs/guides/WRAPPER_BOOTSTRAP.md`](docs/guides/WRAPPER_BOOTSTRAP.md) | Checklist for building per-device bridge scripts |
| [`config/README.md`](config/README.md) | Instructions for local configuration |

Start with the overview, then dive into the architecture and roadmap before touching code.

## Quick Start

**Launch GUI (recommended):**
```bash
python src/goed_gui_v3.py
```

**Supervisor CLI:**
```bash
python src/supervisor_cli.py start all
python src/supervisor_cli.py status
python src/supervisor_cli.py stop all
```

**Sequence Runner:**
```bash
python src/run_cli.py run --plan examples/example_sequence.yaml [--dry-run]
python src/run_cli.py show runs/<run_dir>
python src/run_cli.py resume <checkpoint.json>
python src/run_cli.py find-checkpoints
```

**2WE Dashboard (dual potentiostat):**
```bash
python src/goed_gui_2we_v3_scaffold.py
```

## Current Capabilities

| Capability | Status | Details |
|------------|--------|---------|
| Multi-device orchestration | Complete | Gamry + PI XYZ + Thorlabs + Perimax via subprocess isolation |
| GUI dashboard | Complete | `src/goed_gui_v3.py` (modular, recommended) |
| Gamry techniques (1WE) | Complete | CV, LSV, CA, CP, OCV, EIS, Cell OFF Wait — streaming plots, pause/resume/stop |
| Gamry techniques (2WE) | Complete | Dual-potentiostat pipeline — WE1/WE2 simultaneous execution, STANDBY semantics |
| PI XYZ control | Complete | Home, jog, absolute/relative moves, velocity, park, waypoint sequences |
| Thorlabs camera | Complete | Live view (~8-10 FPS via SharedMemory), snapshots, exposure/gain control |
| Perimax pump | Complete | Speed/direction control, start/stop, serial auto-detection |
| Sequence builder | Complete | Mixed Gamry + PI sequences, array mode (XYZ grid), import/export JSON |
| Live sequence editing | Complete | Edit/add/delete/reorder pending steps during execution (shadow sequence pattern) |
| Checkpoint/Resume | Complete | Atomic checkpoints, GUI resume dialog, CLI resume, orphan detection |
| Analysis module | Complete | Session browser, metrics (peaks, charge, EIS), multi-technique plotting, CSV/PNG export |
| Resource monitoring | Complete | Memory/disk warnings, command watchdog, frame backpressure |
| Device registry | Complete | Unified `device.execute_async()` pattern for all panels |

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                    Main Process (GOED GUI)                       │
│  - PySide6 UI only, no SDK imports                              │
│  - SupervisorService manages all device subprocesses            │
│  - DeviceRegistry: unified execute_async() for all panels       │
└────────┬────────────────┬────────────────┬────────────────┬────┘
         │                │                │                │
    JSON + SHM       JSON only        JSON only       JSON/Serial
         │                │                │                │
         ▼                ▼                ▼                ▼
┌────────────────┐ ┌──────────────┐ ┌──────────────┐ ┌──────────────┐
│ Thorlabs       │ │ PI XYZ       │ │ Gamry        │ │ Perimax      │
│ Wrapper        │ │ Wrapper      │ │ Wrapper      │ │ Wrapper      │
│ ────────────── │ │              │ │              │ │              │
│ pylablib SDK   │ │ pipython SDK │ │ ToolkitPy    │ │ pyserial     │
│ SharedMemory   │ │ JSON IPC     │ │ Py 3.7-32    │ │ RS485 serial │
│ frames         │ │              │ │ External repo│ │              │
└────────────────┘ └──────────────┘ └──────────────┘ └──────────────┘
     Isolated          Isolated          Isolated          Isolated
```

**Key patterns:**
- **Process isolation:** All devices in subprocesses — SDK crashes don't affect GUI or other devices
- **SharedMemory ring buffer:** Lock-free SPSC for Thorlabs live view frames (zero-copy numpy)
- **Circuit breaker:** Failure detection with CLOSED→OPEN→HALF_OPEN state machine
- **Shadow sequence:** Dual-list live editing — edits staged, applied atomically between steps
- **Checkpoint/resume:** Atomic JSON persistence (tmp→bak→final) for long-run recovery

## GUI Features

**Main GUI (`goed_gui_v3.py`):**
- Device tabs: Gamry (7 technique panels), PI XYZ (jog/home/move), Thorlabs (live view/snapshot), Perimax (pump control)
- Sequence builder: Mixed mode (Gamry + PI interleaved) and Array mode (XYZ grid sampling)
- Real-time streaming plots (PyQtGraph, 20 Hz update)
- Live sequence editing during execution
- Profile dialog (operator, sample_id, electrodes)
- Hardware status bar with device health indicators
- Pause/Resume/Stop with proper cell-off safety

**2WE Dashboard (`goed_gui_2we_v3_scaffold.py`):**
- Dual-potentiostat workflow (WE1 + WE2 simultaneous)
- Per-electrode technique selection and PStat context
- STANDBY semantics (cell OFF, no logging, auto-follow duration)
- Dual plot panels (WE1 and WE2)

**Analysis (`src/analysis/analysis_window.py`):**
- Session browser with run history
- Metrics: peak detection, charge integration, EIS impedance
- Multi-technique comparison plotting
- CSV/PNG/JSON export

## Active Files

**GUI entry points** (launchers at `src/` root delegate to `src/entrypoints/`):
- `src/goed_gui_v3.py` → `src/entrypoints/goed_gui_v3.py` — Main GUI (recommended)
- `src/goed_gui_2we_v3_scaffold.py` → `src/entrypoints/goed_gui_2we_v3_scaffold.py` — 2WE dashboard
- `src/goed_gui_v2.py` → `src/entrypoints/goed_gui_v2.py` — Legacy GUI (still functional)
- `src/supervisor_cli.py` → `src/entrypoints/supervisor_cli.py` — Supervisor CLI
- `src/run_cli.py` → `src/entrypoints/run_cli.py` — Sequence runner CLI

**Device wrappers:**
- `scripts/thorlabs_bridge.py` — Thorlabs camera (GOED internal)
- `scripts/pi_bridge.py` — PI XYZ stages (GOED internal)
- `scripts/perimax_bridge.py` — Perimax pump (GOED internal)
- Gamry bridge lives in external repo: `Gamry/scripts/goed_bridge.py`

**Device classes:** `src/devices/`
- `GamryDevice`, `PIWrapperDevice`, `ThorlabsWrapperDevice`, `PerimaxWrapperDevice`
- `DeviceRegistry`, `ThreadSafeDevice`, `CommandResult`

**Supervisor & orchestration:**
- `src/supervisor/device_supervisor.py` — Device lifecycle management
- `src/supervisor/supervisor_service.py` — QThread supervisor wrapper
- `src/sequence/sequence_runner.py` — Sequence execution engine
- `src/sequence/technique_schemas.py` — Technique parameter schemas
- `src/sequence/action_mapper.py` — Command builder

**Control panels:** `src/gui/panels/`
- `gamry_control_panel_v2.py` — Gamry (1WE)
- `gamry_2we_control_panel.py` — Gamry (2WE)
- `pi_control_panel.py` — PI XYZ
- `thorlabs_control_panel_v2.py` — Thorlabs camera
- `perimax_control_panel.py` — Perimax pump

**Executors:** `src/executors/`
- `GamrySequenceExecutor` — 1WE technique sequences
- `Gamry2WESequenceExecutor` — 2WE dual-electrode sequences
- `MixedSequenceExecutor` — Gamry + PI interleaved
- `ArrayModeExecutor` — Gamry sequence at each XYZ position

**Analysis:** `src/analysis/`
- `AnalysisWindow`, `ImportController`, `MetricsCalculator`, `PlotCanvas`

## Vendor Suite Installers (New PC)

For lab onboarding, vendor install assets are standardized under:

`D:\SEM\GOED\installation`

- PI official suite packages: stored in this installation directory (PI subfolder).
- Thorlabs official suite packages: stored in this installation directory (Thorlabs subfolder).
- Gamry installation guidance: stored in this installation directory (Gamry guidance/docs).
- Perimax (Spetec) vendor software: `C:\Program Files (x86)\Spetec\SMC01-Control\`

Install vendor suites/drivers with Administrator privileges. Python, virtual environments, and normal GOED runs should use a standard user context.

## Daily Session Init

Follow [`docs/README_DAILY.md`](docs/README_DAILY.md) to initialize the session and verify environment before coding.

## References

- [`docs/ROADMAP.md`](docs/ROADMAP.md) — Phase 8 complete, Phase 9+ roadmap
- [`docs/guides/DEVICE_INTEGRATION_GUIDE.md`](docs/guides/DEVICE_INTEGRATION_GUIDE.md) — Architecture details
- [`docs/guides/GAMRY_HARDWARE_SOP.md`](docs/guides/GAMRY_HARDWARE_SOP.md) — Safety protocols for hardware sessions
- [`docs/features/LIVE_SEQUENCE_EDITING_PLAN.md`](docs/features/LIVE_SEQUENCE_EDITING_PLAN.md) — Live editing architecture
- [`docs/schemas/SEQUENCE_SCHEMA.md`](docs/schemas/SEQUENCE_SCHEMA.md) — Sequence YAML format
- [`docs/schemas/WRAPPER_IO.md`](docs/schemas/WRAPPER_IO.md) — Wrapper IPC protocol
