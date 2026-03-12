# Roadmap & Timeline

## Current Capabilities (as of 2026-03-10)

| Capability | Status | Details |
|------------|--------|---------|
| Multi-device orchestration | Complete | Gamry + PI XYZ + Thorlabs + Perimax + Force Sensor via subprocess isolation |
| GUI dashboard | Complete | `src/goed_gui_v3.py` (launcher → `src/entrypoints/goed_gui_v3.py`) |
| Gamry techniques (1WE) | Complete | CV, LSV, CA, CP, OCV, EIS, Cell OFF Wait — streaming plots |
| Gamry techniques (2WE) | Complete | Dual-potentiostat pipeline — WE1/WE2 simultaneous execution |
| PI XYZ control | Complete | Home, jog, absolute/relative moves, velocity control |
| Thorlabs camera | Complete | Live view (8-10 FPS), snapshots, exposure/gain control |
| Perimax pump | Complete | Speed/direction control, start/stop, serial auto-detection, 1WE + 2WE GUI |
| Sequence builder | Complete | Mixed Gamry + PI sequences, array mode, import/export JSON |
| Device registry | Complete | Unified `device.execute_async()` pattern for all panels |
| Checkpoint/Resume | Complete | GUI resume dialog, CLI resume, orphan detection |
| Resource monitoring | Complete | Memory/disk warnings, command watchdog, frame backpressure |
| Live sequence editing | Complete | Edit pending steps during execution via shadow sequence pattern |
| Force sensor | Complete (1WE) | I-7016 DCON — real-time streaming, live banner reading, zero offset |
| Src organization | Complete | Domain subdirectories, 6 launcher wrappers at `src/` root |

**Current branch:** `2we` — Active development continues here

### 2WE / STANDBY Semantics Update (2026-02-24, branch `2we`)

- Added universal Gamry `CELL_OFF_WAIT` technique path for cell-OFF timed waits without voltage/current logging.
- 1WE v3 GUI exposes this no-logging wait as user-facing `STANDBY` (backend remains `run_cell_off_wait` for compatibility).
- 2WE `STANDBY` redefined from OCV-like logging hold to `cell OFF + no logging`, preserving EIS pairing semantics (`EIS + STANDBY`).
- 2WE `STANDBY` now supports `duration_s` + `auto_follow_duration` (default auto-follow, manual override allowed).
- 2WE export/merge handling updated so standby-side empty artifacts do not break EIS exports when the active WE produces data.
- See prep/spec: `docs/2we/CELL_OFF_WAIT_IMPLEMENTATION_PREP_2026-02-24.md`

### 2WE Delivery Update (2026-02-12, branch `2we`)

- Consolidated GOED 2WE orchestration with shared controllers:
  - run preflight/profile contract (`gamry_2we_run_controller.py`)
  - wrapper ACK/NACK control flow (`gamry_2we_control_flow_controller.py`)
  - dual-device assignment model (`gamry_2we_device_assignment_controller.py`)
- Updated 2WE GUI connection workflow to assignment-based WE1/WE2 device mapping using discovered devices.
- Added GOED-side `list_devices` command support in `src/devices/gamry_device.py` with graceful fallback when bridge support is absent.
- Full parity gap analysis (G01-G10) implemented: STANDBY/EIS gating, mirror/timing sync, sequence edit/update/duplicate/PStat overrides, streaming key normalization, per-WE enum fidelity, assign/unassign semantics, overlay plot toggle, bootstrap logging, legacy panel deprecation.
- **Hardware validated (2026-02-12)**: 2 potentiostats running simultaneously, all 6 major techniques (CV, LSV, CA, CP, OCV, EIS) confirmed producing data in 2WE pipeline.

### 2WE Analysis Module Integration (2026-02-19, branch `2we`)

- Analysis module now fully supports 2WE pipeline data: discover, load, browse, and plot WE1/WE2 datasets
- Dual-mode manifest parsing with 3-level technique fallback (manifest fields → sequence_definition.json → WE directory filename scan)
- `AnalysisDataset.electrode` field propagates WE identity through the full load → display → plot pipeline
- Legend show/hide toggle ("Labels" checkbox) on both plot canvases
- 34 new tests in `tests/test_analysis_2we.py`; 86 total analysis + regression tests pass
- See report: `docs/2we/2WE_ANALYSIS_MODULE_GAP_REPORT_2026-02-19.md`

### 2WE Stability Update (2026-02-13, branch `2we`)

- Regression fix: assignment designation now consistently shows model/serial instead of generic `PSTAT` labels.
- Regression hardening: 2WE device identity parsing is explicitly section-first to preserve dual-device discovery when wrappers emit duplicate generic tags.
- Added guardrail UX for wrapper incompatibility: `list_devices` unsupported now surfaces a clear warning/status instead of silently masking multi-device limitations.
- Added targeted tests for bridge-style `list_devices` payload shape (duplicate `tag`, unique `section`) to prevent future friendly-fire regressions.
- See reports:
  - `docs/2we/2WE_PLUGIN_SKILL_INVENTORY_2026-02-13.md`
  - *(archived)* `2WE_PSTAT_DESIGNATION_REGRESSION_FIX_2026-02-13.md`

---

## Phase Overview

| Phase | Target Duration | Goal | Key Deliverables | Exit Criteria |
| --- | --- | --- | --- | --- |
| 0. Foundations | Week 1 | Document everything (this repo) & confirm environments | README, overview, device portfolio, architecture, setup guide | Docs reviewed; repo paths verified on both laptops |
| 1. Wrapper Prototypes | Weeks 2-3 | Create minimal wrappers for each device (mock mode allowed) | CLI wrappers that accept JSON commands and respond | Each wrapper can echo `ping` and `status` commands; logs stored locally |
| 2. IPC + Supervisor | Weeks 4-5 | Implement GOED supervisor layer & message bus | Process launcher, heartbeat monitoring, config loader | GOED can start/stop wrappers, send ping, handle restart, display status CLI |
| 3. Sequence Engine | Weeks 6-7 | Build state machine + manifest builder | Run-plan schema, sequence executor, combined manifest output | Dry-run sequence (mock devices) completes end-to-end, manifest produced |
| 4. GUI Integration | Weeks 8-9 | Develop operator GUI (PySide6) with live status | Dashboard, log viewer, manual controls, error dialogs | Operator can trigger dry-run sequence via GUI and monitor statuses |
| 5. Hardware Bring-up | Weeks 10-12 | Connect real devices sequentially | Wrapper updates to call real APIs, hardware safety tests | Each device validated individually via GOED commands |
| 6. Full System Test | Weeks 13-14 | Run complete experiment with all hardware | Test scripts, SOPs, run reports | Combined run executes without manual recovery steps; artifacts linked |
| 7. Gamry Application Integration | Weeks 15-18 | Mirror `echem.app.main` capabilities inside GOED | Capability `describe` RPC, GamryRunner adapter, GUI technique panels for OCV/Chrono/CV/LSV/EIS, orchestrator-backed execution | Operators launch any Gamry technique from GOED and receive the same manifests/CSVs as the native app |
| 8. PI XYZ Stage Automation | Weeks 19-20 | Integrate `PI_Control_System` services for automated motion | StageController (connect/home/move absolute & relative/park/stop/emergency), GUI jog + absolute controls, sample-position schema | Gamry sequences interleave PI moves; manifests include `PI_XYZ/logs/positions_*.json` artifacts |
| 9. Thorlabs Imaging Integration | Weeks 21-22 | Control cameras for inspection & feedback | CameraController (start_live/stop_live/set exposure+gain+ROI/snapshot), preview tiles, QC metrics in manifests | GOED gates steps based on camera feedback; snapshots saved with absolute paths |
| 10. Telemetry Bus & Live Plots | Weeks 23-24 | Stream data for visualization and rules | ZeroMQ (or similar) pub/sub, telemetry schema (Gamry decimated I/V, PI positions @10 Hz, camera FPS/intensity), GUI plots | Sustained 10 Hz telemetry with no drops; plots visible in GUI |
| 11. Reactive Orchestration | Weeks 25-27 | Add condition/trigger support across devices | Rule DSL (`when metric condition -> action`), safety interlocks, manifest rule log | Cross-device rules (camera defect → skip sample, Gamry drift → re-home PI) fire within 250 ms |
| 12. Multi-Sample Workflow & Data Model | Weeks 28-30 | Automate plates/arrays & enrich manifests | Plate definition schema, sequence compiler, artifact catalog referencing native paths | Automated run over ≥16 samples with per-sample telemetry/artifacts |
| 13. Reliability & Regression | Weeks 31-32 | Harden supervisor + add automated tests | Supervisor persistence, wrapper resurrection scripts, simulators + HIL regression | Yank/replug recovery verified; nightly sim suite passes |
| 14. Handoff & Hardening | Ongoing | SOPs, installers, backlog for remote/cloud | Operator manuals, packaging, backlog for future automation | Two operators reproduce reactive multi-device runs via SOP without developer help |

## Milestone Details

### Phase 0 – Foundations
- Capture architectural intent before coding.
- Confirm repository availability on both laptops.
- Outcome: This documentation repo synced and understood by future Codex agents.

### Phase 1 – Wrapper Prototypes
- Implement `--mock` or simulated versions first.
- Define JSON schemas for commands/responses.
- Provide `README` inside each device repo (or `device_wrappers/`) describing launcher usage.

### Phase 2 – IPC + Supervisor
- Choose transport (stdin/stdout vs ZeroMQ). Start with pipes for simplicity.
- Build heartbeat mechanism (`{"action": "ping"}` every few seconds).
- Implement exponential backoff for restarts, with operator alerts.

### Phase 3 – Sequence Engine
- Define `sequence.yaml` structure (steps array, dependencies, retry policies).
- Implement manifest aggregator linking each device’s output paths.
- Add dry-run mode that simulates durations without touching hardware.

### Phase 4 – GUI Integration
- Layout suggestion:
  - Left: sequence tree/status.
  - Middle: per-device tiles with key telemetry.
  - Right: log pane + command buttons.
- Provide keyboard shortcuts for start/pause/abort.

### Phase 5 – Hardware Bring-up
- Order: PI stages → Thorlabs camera → Gamry (most fragile).
- For each device:
  1. Run wrapper standalone with real hardware.
  2. Execute same commands via GOED.
  3. Update `DEVICE_PORTFOLIO.md` if requirements changed.

### Phase 6 - Full System Test
- Create canonical test sequence (e.g., stage move, camera focus check, Gamry CV run).
- Capture data artifacts and verify timestamp alignment.
- Run twice on two laptops to ensure reproducibility.

### Phase 7 - Gamry Application Integration

**Status (2025-11-28):** P5 Rolling Window & GUI Polish COMPLETE – Full Gamry parity achieved

#### Completed
- ✅ All technique panels (CV, LSV, CA, CP, OCV, EIS) with full parameter UI
- ✅ EIS supports both PSTAT and GSTAT modes
- ✅ LSV native action (not CV alias)
- ✅ CommandDispatcher for async non-blocking execution
- ✅ Describe schema validation with static fallback
- ✅ Session folder creation and manifest generation
- ✅ Multi-device tabs (Gamry/PI/Thorlabs)
- ✅ Profile Dialog with index persistence (`src/widgets/gamry_profile_dialog.py`)
- ✅ Profile dialog integration in control panel
- ✅ Method Panel with Run Sequence button
- ✅ Sequence execution via CommandDispatcher (sequential step dispatch)
- ✅ Per-step state tracking UI (pending/running/done/failed icons)
- ✅ Sequence Import/Export (JSON files)
- ✅ Async wrapper architecture (v0.3.0) for responsive operation
- ✅ EC Plot Widget with autoscaling and technique views
- ✅ Real-time streaming plots (P1.5) with PlotController backend
- ✅ Export features (P1.6): sequence-info.txt, PNG plots, EIS 3-panel

#### Remaining Work (Prioritized)

**P1 – Must Have for Tk Parity:** _Completed 2025-11-25_
1. ~~**Profile Dialog**~~ – ✅ Complete
2. ~~**Method Panel Execution**~~ – ✅ Complete
3. ~~**Sequence Import/Export**~~ – ✅ Complete
4. ~~**Sequence Folder Structure**~~ – ✅ Complete
5. ~~**Multi-Step Plotting**~~ – ✅ Complete
6. ~~**Profile in Manifest**~~ – ✅ Complete
7. ~~**Streaming Plots (P1.5)**~~ – ✅ Complete
8. ~~**Export Features (P1.6)**~~ – ✅ Complete (sequence-info.txt, PNG plots)

**P2 – Should Have:** _Completed 2025-11-26_
4. ~~**PStat Context Application**~~ – ✅ Complete
5. ~~**Per-step PStat Overrides**~~ – ✅ Complete
6. ~~**Pause/Resume Documentation**~~ – ✅ Complete

**P3 – Completed 2025-11-27:**
7. ~~**Warning Bar**~~ – ✅ Complete (pre-flight validation with hardware_lib)
8. ~~**Advanced PStat Dialog**~~ – ✅ Complete (implemented in P2)
9. ~~**Vocv Baseline Management**~~ – ✅ Complete (display-only, persistent status bar)

**P4 – Pause/Resume/Stop (COMPLETE 2025-11-28):**

_Core Features:_
10. ✅ Pause/Continue/Stop buttons with state machine (IDLE → RUNNING → PAUSED)
11. ✅ pause_task/continue_task/stop_task wrapper commands in goed_bridge.py
12. ✅ GoedTechniqueRunner pause/resume/stop API with _active_orchestrator tracking
13. ✅ run_remaining_cycles() for multi-cycle CV/LSV continuation after pause
14. ✅ task_interrupted event (user stop without error popup)
15. ✅ command_interrupted signal in CommandDispatcher
16. ✅ PausedException special handling (keeps task_state="running" so stop works)

_Bug Fixes (2025-11-28):_
17. ✅ Stop while paused emits task_interrupted (not task_error) – clean UI reset
18. ✅ Stop terminates entire CV/LSV step – uses _stop_triggered flag in orchestrator
19. ✅ Button state properly resets for subsequent runs – use set_state() not _on_state_changed()
20. ✅ Cell OFF forced on stop during multi-cycle CV – safety fix in orchestrator.py finally block
21. ✅ Sequence pause/continue/stop with proper cleanup – _finish_gamry_sequence(), _cleanup_gamry_sequence_state()
22. ✅ Sequence list preserved during runs – skip _refresh_manifest_view during Gamry sequences

**P5 – Rolling Window & GUI Polish (COMPLETE 2025-11-28):**

_Rolling Window (RT UX):_
23. ✅ ROLLING_WINDOW_S_DEFAULT per-technique defaults (OCV=120s, others=0)
24. ✅ rolling_window_s attribute and set_rolling_window() API in ECPlotWidget
25. ✅ _apply_rolling_window() for time-based plots (V vs t, I vs t)
26. ✅ Rolling Window UI controls in GamryControlPanel (entry + Apply button)
27. ✅ rolling_window_changed signal wired to plot widget
28. ✅ _update_rtux_visibility() enables controls only for OCV/CA/CP

_Bug Fixes:_
29. ✅ OCV/CP plot visibility fix – autoscale now uses correct data matching view
30. ✅ PI/Thorlabs panels wrapped in QScrollArea for proper splitter collapse

_GUI Polish:_
31. ✅ Renamed "Sequence Steps" to "Sequence Manager"
32. ✅ Splitter collapse at 70% threshold with elastic resistance
33. ✅ Colored state icons (gray=pending, blue=running, green=done, red=failed, orange=stopped)
34. ✅ Green "Running..." text on Run button during execution

_Deferred:_
- Device Panel – Fake/Real device toggle, connect/disconnect buttons
- Minor Polish – Duplicate step deep copy, on-closing pause warning

#### Exit Criteria
- Operators can configure/run any Gamry technique from GOED GUI
- Profile dialog captures metadata before each run
- Sequences can be built, saved, loaded, and executed from GUI
- Manifests match Gamry Tk app structure

**See:** `docs/PHASE7_GAP_CHECKLIST.md` for detailed task checklist
### Phase 8 - Full Process Isolation (native branch)

**Status (2025-12-03):** ✅ Section 9 Complete - Unified device_registry architecture

**See:** `docs/guides/DEVICE_INTEGRATION_GUIDE.md` for architecture details

**Branch:** `native` — Primary development branch (permanent). All future development continues on this branch. No merge to `master` planned.

This phase implements full process isolation to resolve USB/DLL conflicts between PI and Thorlabs SDKs.

#### Background
- Native PI integration was archived due to USB conflicts with Thorlabs SDK
- `thorlabs_tsi_usb_hotplug_monitor.dll` detects USB changes from PI operations
- Solution: All devices use wrapper/subprocess for complete isolation

#### Architecture: Hybrid Dual-Channel

| Device | Control Channel | Data Channel | Rationale |
|--------|-----------------|--------------|-----------|
| Thorlabs | stdin/stdout JSON | Shared Memory (frames) | High bandwidth video |
| PI XYZ | stdin/stdout JSON | stdin/stdout JSON | Low bandwidth |
| Gamry | stdin/stdout JSON | stdin/stdout JSON | Low bandwidth |

#### Completed
- ✅ **Device Abstraction Layer** (`src/devices/`)
  - `base.py` - DeviceState, CommandResult, Device interface
  - `thread_safe_device.py` - Worker thread with command queue pattern
  - `registry.py` - DeviceRegistry for centralized device management
- ✅ **ThorlabsDevice** (native, temporary) - `src/devices/thorlabs_device.py`
- ✅ **Native camera module** - `src/camera/` (controller, adapter, models)
- ✅ **Architecture analysis** - IPC options evaluated, hybrid design selected
- ✅ **Documentation** - DEVICE_INTEGRATION_GUIDE.md updated with plan

#### WP1: Thorlabs Wrapper (JSON-only) ✅ Complete
**Goal:** Validate process isolation resolves USB conflicts

- ✅ Create `scripts/thorlabs_bridge.py` wrapper script
  - Uses GOED's `src/camera/` module internally
  - Conforms to `docs/schemas/WRAPPER_IO.md` protocol
  - Commands: ping, status, shutdown, connect, disconnect
  - Commands: snapshot, set_exposure, set_gain
- ✅ Update `config/device_paths.yaml` with Thorlabs wrapper config
- ✅ Create `src/devices/thorlabs_wrapper_device.py`
  - Wrapper-based device using DeviceSupervisor
  - Replaces native ThorlabsDevice for process isolation
- ✅ Update `src/gui/panels/thorlabs_control_panel_v2.py` to use wrapper device
- ✅ Test: All three devices running simultaneously without conflicts

#### WP2: Shared Memory Live View ✅ Complete
**Goal:** Restore full live view with process isolation

- ✅ Implement SharedMemory ring buffer for frames (`src/camera/shared_memory.py`)
  - Uses `multiprocessing.shared_memory` (Python 3.8+ stdlib)
  - Lock-free SPSC (single-producer single-consumer) pattern
  - Header: write_idx, frame_count, width, height, channels, dtype
- ✅ Add `start_live`/`stop_live` commands to wrapper
  - Returns `shm_name` for main process to attach
  - Frame reader thread polls shared memory
- ✅ Update panel to read frames from shared memory
  - Zero-copy numpy view for maximum performance
- ✅ USB coordination: Thorlabs pauses during PI USB operations
- ✅ Event logging system for multi-device debugging
- ⚠️ FPS ~8-10 (vs 30+ in official software) - tracked for future optimization

#### WP3: Integration & Validation ✅ Complete
**Goal:** Full multi-device operation with process isolation

- ✅ USB coordination: Camera controls disabled during PI USB operations
- ✅ Auto-exposure reduction for live view (20ms default)
- ✅ Frame fetcher optimization (conditional sleep)
- ✅ Hardware validation with all three devices (Thorlabs + PI XYZ + Gamry)
- ✅ Live view stable during PI movements and Gamry measurements
- ✅ Test artifacts: `tests/manual/test_wp3_integration.py`, `tests/manual/GUI_VALIDATION_WP3.md`
- 📋 Future: PI XYZ movements as sequence steps (see Future Enhancements)

#### Phase 3: PI XYZ Wrapper Consolidation ✅ Complete (Optional)
**Goal:** Move PI wrapper into GOED for unified codebase

- ✅ Create `scripts/pi_bridge.py` using GOED's `src/pi/` module
  - Commands: ping, status, shutdown, connect, disconnect, home_all, home_axis
  - Commands: get_position, move_absolute, move_relative, stop, set_velocity
  - Commands: park_all, run_sequence, cancel_sequence
  - Backwards compatible with external wrapper's single-axis move format
- ✅ Update `config/device_paths.yaml` with both external/internal PI options
- ✅ Hardware validation: connect, home, move, stop, shutdown all working
- Both options available: external (PI_XYZ repo) or internal (GOED's src/pi/)

#### Section 9: Unified device_registry Architecture ✅ Complete
**Goal:** All panels use same communication pattern as ThorlabsControlPanelV2

- ✅ Create `src/devices/pi_wrapper_device.py` - PIWrapperDevice following ThorlabsWrapperDevice pattern
- ✅ Update `src/devices/__init__.py` - Export PIWrapperDevice
- ✅ Migrate `src/gui/panels/pi_control_panel.py` to device_registry pattern
  - Accepts `device_registry` instead of `supervisor_service`
  - Uses `device.execute_async()` with callbacks
  - Thread-safe UI updates via `_device_result` signal
- ✅ Migrate `src/gui/panels/gamry_control_panel_v2.py` to device_registry pattern
  - Accepts `device_registry` (with supervisor_service fallback)
  - Routes technique commands through GamryDevice when available
  - No changes to technique panels (cv_panel.py, chrono_panel.py, etc.)
- ✅ Update `src/goed_gui_v2.py` - Register PI and Gamry devices in registry
- ✅ Hardware validation: PI XYZ and Gamry work correctly via device_registry
- ✅ USB resilience fix (2025-12-03): Thorlabs survives PI jog operations
  - Adaptive polling backoff (10ms → 50ms → 100ms → 500ms) when frames stop
  - Fixed race condition where Start Live button was re-enabled during USB operations
  - Added stall detection in wrapper to recover from frozen streams

#### Exit Criteria ✅ Achieved
- ✅ All three devices run simultaneously without USB/DLL conflicts
- ⚠️ Thorlabs live view works at ~8-10 FPS via shared memory (30 FPS tracked for future)
- ✅ Device crashes don't affect GUI or other devices
- ✅ Thorlabs survives PI jog operations without crashing
- 📋 Sequences can interleave Gamry techniques with PI moves (future enhancement)

#### PI XYZ Sequence Integration (2025-12-04)
- **Status**: COMPLETE - Mixed sequences and single runs fully functional
- ✅ PI step dialogs: Move Absolute/Relative, Home, Set Velocity, Park, Waypoint Sequence
- ✅ SequenceTableWidget extended with PI step menu
- ✅ Mixed sequence execution engine (`_run_mixed_sequence`)
- ✅ Pre-run validation (`src/sequence/sequence_validator.py`)
- ✅ Cross-thread signal for PI step completion
- ✅ Post-sequence cleanup: `_on_command_interrupted_dispatcher` handles mixed sequences
- ✅ State reset: `is_adhoc_sequence` properly cleared in `_finish_mixed_sequence`
- ✅ Gamry panel: Connection check with supervisor fallback path
- ✅ PI panel: Status label for visual feedback, fixed move_absolute parameters
- ✅ Single device runs (Gamry/PI) work correctly after mixed sequences

#### Future Enhancements (tracked)
- **FPS Optimization**: Investigate pylablib frame polling vs callbacks
- **Thorlabs Sequence Steps**: Add camera operations to sequence builder

---

### Post-Phase 8: Reliability Branch (2025-01)

**Status:** Active development on `reliability` branch

**Branch:** `reliability` — Primary development branch (no merge to `native` or `master` planned)

#### February 2026 Milestones (Phase 9.5 - Live Sequence Editing)
- ✅ **Live Sequence Editing** - Edit pending steps during execution
  - **Status**: COMPLETE — Implementation done, executor integration bugs fixed, hardware validated
  - **See**: `docs/features/LIVE_SEQUENCE_EDITING_PLAN.md` for full plan
  - **Architecture**: Shadow Sequence Pattern + UUID step identity
  - **Capabilities**:
    - [x] Edit technique parameters for pending steps
    - [x] Edit PStat/context parameters for pending steps
    - [x] Add new steps after current executing step
    - [x] Delete pending steps during execution
    - [x] Reorder pending steps during execution
    - [x] Tracking arrays resize after structural edits (insert/delete)
    - [x] Checkpoint resume initializes shadow sequence for live editing
- ✅ **Analysis Session Refresh + Artifact Resolution**
  - Analysis session list updates after each completed step
  - Manifest writer resolves missing artifact paths to prevent empty plots/exports
- ✅ **2WE Long-Run Truncation Hardening (Cycle-42 repeat stop)**
  - Root cause investigated and documented (`docs/2we/2WE_CYCLE42_REPEATABLE_TRUNCATION_INVESTIGATION_2026-02-25.md`)
  - GOED CV/LSV sample rate UI now derived/read-only from `scan_rate / step_size_V`
  - External Gamry wrapper patched for dynamic curve buffer sizing, CV sampling normalization, timing-underrun detection, and 2WE mixed-cycle corrected completion reporting
  - Hardware rerun validation pending on real instrument setup

#### January 2026 Milestones
- ✅ Checkpoint/Resume Phase 1: Checkpoint persistence for all executors
- ✅ USB Disconnect Detection: Circuit breaker integration, hardware error detection, user notification popup
- ✅ Resource Monitoring (Phase 3A): Memory/disk monitoring with Qt signals and GUI toast warnings
- ✅ Command Watchdog (Phase 3B): Stuck command detection in supervisor heartbeat loop
- ✅ Frame Backpressure (Phase 3C): Camera stream stability with pending frame tracking

#### January 2025 Milestones
- ✅ Heartbeat latency trending and health score metrics
- ✅ Hardware status bar with real-time device status polling
- ✅ EIS PNG export for sequence runs
- ✅ Thorlabs serial number display (model + S/N like Gamry)
- ✅ Fixed Thorlabs panel false "Connected" state

#### December 2024 Milestones (late Phase 8)
- ✅ PI XYZ sequence integration (mixed Gamry + PI sequences)
- ✅ Mixed sequence export with unified folder structure
- ✅ USB resilience: Thorlabs survives PI jog operations
- ✅ Unified device_registry architecture (Section 9)
- ✅ PI velocity GUI control fix

---

### Phase 9 - Thorlabs Imaging Integration (Future)
- Expand `Thorlabs/scripts/goed_bridge.py` to wrap `src/app/controller.py` methods: `start_live`, `stop_live`, `set_exposure`, `set_gain`, `set_white_balance`, `set_roi`, preset save/load, `snapshot`, status/FPS/error reporting.
- Support multi-camera setups via multiple config entries (e.g., `thorlabs_primary`, `thorlabs_macro`) with dedicated DLL paths/presets.
- Imaging capability schema documents exposure/gain ranges, ROI bounds, supported binning, QC metrics (intensity histogram, focus score from `services/focus_assistant.py`), and snapshot artifact metadata.
- GOED GUI hosts camera tiles: live preview (QImage), histogram overlay, QC indicators, preset dropdown, “inspect before measure” toggle feeding into rules.
- Exit when GOED can start/stop live view, adjust settings, capture snapshots with absolute paths, log QC metrics in manifests, and gate sequence steps based on camera health without manual intervention.
### Phase 10 - Telemetry Bus & Live Plots
- Stand up a pub/sub telemetry bus (ZeroMQ recommended) so wrappers stream data outside the request/response channel:
  - Gamry: decimated I/V/time samples + overload flags from `Orchestrator._on_row`.
  - PI: position/velocity vectors at 10 Hz, force sensor readings, motion state.
  - Thorlabs: FPS, intensity histograms, focus metrics, acquisition errors.
- Document payloads in `docs/schemas/TELEMETRY.md`; update `device_supervisor.py` with subscriber threads, bounded queues, and backpressure (drop oldest vs throttle).
- GOED GUI adds live charts and telemetry health indicators plus optional recording/replay (`runs/<id>/telemetry/*.jsonl`).
- Exit when telemetry streams for ≥10 minutes without drops, plots update in real time, and recorded streams replay faithfully for debugging.
### Phase 11 - Reactive Orchestration
- Define a rules DSL (`rules.yaml` or embedded in sequences): `when <device.metric> <comparison> [for duration] then <action>` with guard clauses (rate limits, cooldowns, force interlocks).
- Extend `sequence_runner.py` with a rule engine that consumes telemetry, evaluates conditions, injects actions (skip, retry, trigger device command, pause for operator), and logs outcomes.
- Update manifests with a `rules` section capturing trigger metrics, actions, and timestamps; expose a GUI Rule Builder tied to capability schemas.
- Exit when at least three cross-device rules (e.g., camera QC fail → skip sample, Gamry drift → re-home PI_Z, PI overload → abort Gamry run) execute concurrently with <250 ms latency and full audit trail.
### Phase 12 - Multi-Sample Workflow & Data Model
- Create `docs/schemas/PLATE_SCHEMA.md` describing sample grids (rows/cols/spacing), z-drop, force targets, imaging requirements, per-sample technique lists, skip criteria, and rework instructions.
- Build a compiler that expands plate definitions into GOED sequences (PI move → Thorlabs inspect → Gamry technique block) with optional overlap where hardware permits.
- Enhance manifests with per-sample records: PI positions, QC metrics, Gamry segment references, artifact catalog (CSV, PNG, logs) with absolute paths and sample IDs; add Run Browser tooling to query/export by sample.
- Exit when an unattended ≥16-sample run completes with full sample-level manifests and operators can export per-sample bundles for analysis.
### Phase 13 - Reliability & Regression
- Persist supervisor/device state (PID, start time, last ping, log paths) to disk so `python src/supervisor_cli.py status` (launcher → `src/entrypoints/supervisor_cli.py`) reflects reality even across CLI restarts.
- Implement recovery scripts per device (Gamry Toolkit/licensing prompts, PI USB reconnect + re-home, Thorlabs DLL reload + acquisition restart) and document yank/replug procedures.
- Add simulators/mocks (Gamry fake orchestrator stream, PI mock controller, camera frame generator) wired into CI for regression suites; maintain on-bench HIL smoke tests.
- Exit when nightly simulation runs pass, yank/replug recovery scripts succeed, and supervisor state stays consistent after unexpected restarts.
### Phase 14 - Handoff & Hardening
- Deliver SOPs + troubleshooting trees covering start-up, sequencing, rules tuning, telemetry diagnostics, and recovery flows; reference actual log paths (`Gamry/logs`, `PI_XYZ/logs`, `Thorlabs/logs/app_*.log`).
- Package GOED + dependencies (managed venvs or installers) with version stamping (GOED commit plus each device repo commit) embedded in manifests.
- Provide operator run-report templates, backlog for remote/cloud monitoring, and ensure two operators can execute reactive multi-device runs using only the SOP.
- Exit when documentation + packaging make the system reproducible on new machines without developer assistance.

