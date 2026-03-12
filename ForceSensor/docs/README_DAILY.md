GOED Daily Init Checklist

Purpose: Start a fresh coding/evaluation session with the right context and entry points. Follow these steps before making changes.

## 1WE/2WE Pause-Continue-Stop Hardening Closeout (2026-03-12)

- Closed the still-open pause/continue/stop gaps from `docs/2we/2WE_PAUSE_STOP_GAP_ANALYSIS_2026-02-27.md` across both GOED and the sibling `Gamry` bridge/runtime.
- GOED-side fixes covered:
  - 1WE pause/continue rollback and interrupted-run artifact recovery
  - 2WE single-run and sequence pause/continue/stop state handling
  - per-WE targeted stop checkpoint semantics
  - continue-time canvas refresh and corrected cycle color progression
  - defensive stop completion fallback when bridge callbacks are missing
  - 2WE sequence pause button re-arming across later steps
- Gamry-side fixes covered:
  - 2WE bridge pause-state parity for `continue_task`
  - CV/LSV paused-cycle resume semantics
  - 2WE `EIS + STANDBY` merged export schema handling when one WE has no rows
- Hardware validation status:
  - User validated 1WE and 2WE GUI behavior on connected hardware
  - final blocking issue from the last sequence run was the 2WE `EIS + STANDBY` merged export popup; root cause and fix live in `Gamry/src/echem/core/data_merger.py`
- New docs created:
  - `docs/plans/2026-03-12-pause-stop-gap-implementation.md`
  - `docs/2we/2WE_PAUSE_STOP_VALIDATION_CHECKLIST_2026-03-12.md`

## Gamry Safety Hardening + Force Sensor 2WE + 1WE GUI Improvements (2026-03-12)

- Fixed 2 critical Gamry device safety gaps (ERR-001, ERR-002):
  - `_do_disconnect()` now sends `{"action":"disconnect"}` IPC before killing bridge (Cell OFF safety)
  - Added `_connected_bridge_pid` tracking + auto-reconnect on bridge restart (matches Thorlabs/Perimax pattern)
- Integrated force sensor into 2WE GUI (`goed_gui_2we_v3_scaffold.py`): device init, registry, control panel tab, status bar live reading, display name, failed count 4→5
- Removed meaningless "Session ID" field from 1WE Gamry panel; session IDs now always auto-generated
- Added "Add to Sequence" button to 1WE Gamry panel (next to "Run Technique") — emits `add_step_requested` signal, main window routes to `SequenceTableWidget._add_gamry_step()`

## Force Sensor (I-7016 DCON) Integration (2026-03-10)

- Integrated I-7016 DCON analog input module as 5th GOED device for scanning flow cell contact force monitoring.
- New bridge: `scripts/force_bridge.py` — DCON serial protocol (RS232, 9600 8N1, `#AA\r` → `>+NNNNN.NNNNN`), mock mode, streaming `data_point` events via stdout at configurable Hz.
- New device: `src/devices/force_wrapper_device.py` — `ForceWrapperDevice(ThreadSafeDevice)` with `force_updated` Qt signal, bridge PID restart detection, zero offset, streaming restore after auto-reconnect.
- New panel: `src/gui/panels/force_control_panel.py` — Live PyQtGraph plot, big value display, Zero/Start Stream/Stop Stream/Read Once buttons.
- Config: `config/device_paths.yaml` — `force_sensor` entry (COM8, address 02).
- Wired into 1WE GUI (`goed_gui_v3.py`) as "Force" device tab; 2WE deferred.
- Hardware status banner: Force sensor added as 5th indicator; shows live offset-corrected reading (blue, `±0.XXXX`) during streaming at 5 Hz throttle, falls back to Ready/Offline otherwise.
- Fixed streaming auto-restart bug: added `_serial_lock` for thread-safe DCON queries, ping skips hardware query during streaming (stream proves liveness), device restores streaming after bridge reconnect.
- Investigation report: `docs/force_sensor/FORCE_SENSOR_INTEGRATION_PLAN_2026-03-10.md`

## Post-Refactor Disconnection Scan & Hardening (2026-03-09)

- Comprehensive 6-agent scan (Explore, Silent-Failure-Hunter, Variant Analysis, Function-Analyzer, Differential Review, Sharp-Edges) to find path/import disconnections left by the `src/` restructuring.
- Found 2 active breaks, 3 critical latent issues, 8 high-latent patterns across 33 findings total.
- Fixed `src/gui/theme.py` path resolution for `gui_experimental/` and assets (palette + SVG arrows).
- Eliminated 12 `try/except ImportError` blocks that silently disabled internal GOED modules:
  - `action_mapper.py`: validation bypass returning `(True, "")` → direct import
  - `gamry_sequence_executor.py` + `gamry_2we_sequence_executor.py`: 6 ControlPanelState try/except → module-level import
  - `array_mode_executor.py` + `mixed_sequence_executor.py`: CommandResult import → module-level
  - `sequence_runner.py`: DeviceRegistry/DeviceState/CommandResult → direct import
- Added `logger.warning()` to `splash_screen.py` Theme fallback (legitimate optional, but was silent).
- Replaced hardcoded `C:\Users\AKL\...` Gamry repo path in `gamry_control_panel_v2.py` with config-based resolution from `device_paths.yaml`.
- Investigation reports:
  - `docs/architecture/POST_REFACTOR_DISCONNECTION_SCAN_2026-03-09.md` (master)
  - `docs/architecture/PATH_RESOLUTION_VARIANT_ANALYSIS_2026-03-09.md`
  - `docs/architecture/SRC_REFACTOR_DIFFERENTIAL_REVIEW_2026-03-09.md`
  - `docs/architecture/SHARP_EDGES_POST_RESTRUCTURING_2026-03-09.md`

## 2WE Pause/Continue/Stop Gap Analysis (2026-02-27)

- Comprehensive 1WE vs 2WE pause/continue/stop investigation using multi-tool analysis (Explore, function-analyzer, silent-failure-hunter).
- Produced gap analysis with 18 findings (2 Critical, 5 High, 7 Medium, 4 Low) covering per-WE stop propagation, signal cleanup, panel state resets, between-step pause, and NACK rollback.
- Cross-evaluated against a competing report; retracted one false positive (F6: `super()` MRO behavior) and incorporated one missed 1WE gap (F20: NACK/timeout rollback).
- Updated CLAUDE.md with anti-path-dependence tooling principle requiring comprehensive plugin/skill survey before deep investigations.
- Investigation record: `docs/2we/2WE_PAUSE_STOP_GAP_ANALYSIS_2026-02-27.md`

## 2WE Overlay WE2 Plot Isolation Fix (2026-02-27)

- Fixed overlay data contamination in 2WE GUI so WE1/WE2 data buffers remain isolated even when `Overlay WE2` is enabled.
- Updated 2WE scaffold routing to keep ingestion electrode-scoped (`WE1 -> plot_widget`, `WE2 -> plot_widget_we2`) and treat overlay as display-only.
- Fixed secondary mutation bug in `ECPlotWidget` single-trace autoscale path where overlay redraw extended aliased canonical buffers in-place.
- Added regression tests for:
  - overlay ON keeps WE2 routed to WE2 widget
  - per-WE technique isolation in overlay mode
  - real-widget buffer isolation under synthetic streaming
  - WE2 EIS reset stays scoped to WE2 widget in overlay mode
- Validation: `python -m pytest tests/test_goed_gui_2we_v3_scaffold_routing.py -k "overlay or reset_eis" -v` (11 passed).
- Investigation records:
  - `docs/2we/2WE_OVERLAY_PLOT_BUG_INVESTIGATION_2026-02-27.md`
  - `docs/2we/2WE_OVERLAY_WE1_DATA_MUTATION_FIX_2026-02-27.md`

## Perimax 2WE Integration & Doc Alignment (2026-02-26)

- Added Perimax pump as fourth device in 2WE GUI (`goed_gui_2we_v3_scaffold.py`): device init, registry, control panel tab, display name map
- Added scroll area to Perimax control panel (matches PI/Thorlabs/Gamry panel pattern)
- Fixed Perimax bridge `float()` crash on SMC01 serial responses (`get_info`, `get_status`, `get_position`, `status`) — added `_parse_numeric()` helper to extract numbers from prefixed responses
- Fixed "all devices failed" count in both `goed_gui_v3.py` and `goed_gui_2we_v3_scaffold.py` (3→4 after Perimax addition)
- Aligned all docs with post-refactor `src/` structure (10 files updated for new paths)
- Investigation reports: `docs/perimax/PERIMAX_2WE_GAP_ANALYSIS_2026-02-26.md`, `docs/perimax/PERIMAX_PIPELINE_ARCHITECTURE_2026-02-26.md`

## STANDBY / Cell-Off Wait Delivery (2026-02-24)

- Added universal no-logging cell-off wait backend path (`CELL_OFF_WAIT`) for Gamry sequence execution (GOED + Gamry bridge/orchestrator support).
- 1WE v3 now exposes the no-logging wait mode as a user-facing `STANDBY` tab while preserving internal compatibility with `run_cell_off_wait`.
- 2WE `STANDBY` semantics updated to `cell OFF + no logging` (replacing prior OCV-like logging behavior).
- 2WE `STANDBY` panel now supports user-entered `duration_s` plus `auto_follow_duration` toggle; timing sync honors manual override.
- 2WE EIS + STANDBY export/merge path hardened for empty standby-side artifacts (active EIS side still exports normally).
- Export/session folder naming for `CELL_OFF_WAIT` now aliases to `STANDBY` in GUI single-run paths (v2/v3/2WE-v3/experimental v5).
- Investigation/spec report added: `docs/2we/CELL_OFF_WAIT_IMPLEMENTATION_PREP_2026-02-24.md`

## 2WE Analysis Module Integration (2026-02-19)

- Analysis module now discovers, loads, and plots data from 2WE pipeline sessions
- Dual-mode manifest parsing: `steps` (1WE) and `segments` (2WE) with 3-level technique fallback (manifest → sequence_definition.json → WE directory scan)
- `AnalysisDataset.electrode` field tracks WE1/WE2/None identity through load → display → plot
- Session browser shows WE1/WE2 sub-items under 2WE sessions; preview indicates "(2WE)"
- Legend show/hide toggle ("Labels" checkbox) on both `AnalysisPlotCanvas` and `MultiTechniquePlotCanvas`
- Path resolution handles absolute, relative, and WE-subdirectory artifact paths
- Investigation report: `docs/2we/2WE_ANALYSIS_MODULE_GAP_REPORT_2026-02-19.md`
- Test coverage: 34 tests in `tests/test_analysis_2we.py`
- Files modified: `models.py`, `import_controller.py`, `session_browser.py`, `analysis_window.py`, `plot_canvas.py`, `multi_plot_canvas.py`

## 2WE Display Helpers (2026-02-16)

- Extracted shared display utilities to `src/utils/pstat_display_helpers.py`:
  - `compute_sparse_overrides()` — delta computation against PStat baselines
  - `format_pstat_multiline()` / `format_pstat_2we_column()` — PStat column rendering
  - `format_technique_params()` — technique-specific parameter formatting (OCV, CA, CP, CV, LSV, EIS, STANDBY)
- 2WE PStat column now shows `(default)` when unchanged, sparse overrides with friendly labels when modified (matches 1WE pattern)
- 2WE technique parameter columns now show concise, technique-aware summaries instead of raw `key=val` dumps
- 1WE sequence table `_format_params_multiline()` now handles 2WE steps (detects `2WE ` prefix or `run_2we_manual` action)
- Fixed pre-existing `or` bug in `gamry_2we_sequence_executor.py:591-592` where empty dict `{}` was treated as falsy
- Test coverage: 52 tests in `test_pstat_display_helpers.py`

## 2WE Hardening Note (2026-02-13)

- Fixed 2WE assignment designation regression so WE labels prefer `model-serial` over generic `tag` (avoids meaningless `PSTAT` display).
- Locked 2WE multi-device identity parsing to section-first keys (`section`, `section_tag`, `device_tag`) to prevent duplicate generic tags from collapsing two USB potentiostats into one detected entry.
- Added explicit wrapper capability warning path when `list_devices` is unsupported (`Unknown action: list_devices`) to prevent silent single-device fallback.
- Added regression coverage for bridge-style `list_devices` payload shape (duplicate `tag`, unique `section`) to ensure both WE1/WE2 remain assignable.
- Investigation and verification reports:
  - `docs/2we/2WE_PLUGIN_SKILL_INVENTORY_2026-02-13.md`
  - *(archived)* `2WE_PSTAT_DESIGNATION_REGRESSION_FIX_2026-02-13.md`

## 2WE Branch Note (2026-02-12)

- Branch `2we` now uses assignment-driven dual-potentiostat mapping in GOED 2WE GUI (no manual WE tag text entry).
- Added shared 2WE controllers for run preflight + control flow:
  - `src/controllers/gamry_2we_run_controller.py`
  - `src/controllers/gamry_2we_control_flow_controller.py`
  - `src/controllers/gamry_2we_device_assignment_controller.py`
- 2WE run gate now requires valid WE1/WE2 assignments derived from discovered devices.
- GOED `GamryDevice` now exposes `list_devices` command and falls back to `describe.device_info` if wrapper discovery is unavailable.
- **2026-02-12 Parity gaps G01-G10 addressed** (see `docs/2we/2WE_FULL_PARITY_GAP_ANALYSIS_2026-02-12.md`):
  - Streaming key normalization (`we` → `electrode_id`) at dispatcher boundary
  - STANDBY technique + EIS restriction UI gating
  - WE2 mirror/timing sync from WE1 master
  - Sequence table edit/update/duplicate/PStat override parity
  - Per-WE enum/model fidelity (separate capabilities per assigned device)
  - WE buttons relabeled to Assign/Unassign (matching GOED wrapper semantics)
  - Dual plot overlay toggle, bootstrap event logging, legacy panel deprecation mark, shared table visibility toggle
- **Hardware validated**: 2-potentiostat simultaneous run, all 6 major techniques (CV, LSV, CA, CP, OCV, EIS) produce data in 2WE pipeline

**Note (2026-02-26 refactor):** `src/` root now contains only 6 launcher wrappers that delegate to `src/entrypoints/`. All implementation code lives in domain subdirectories (`supervisor/`, `sequence/`, `gui/panels/`, etc.). CLI commands like `python src/supervisor_cli.py` still work via these launchers. Historical changelog entries below reference pre-refactor paths; see `CLAUDE.md` File Organization section for current layout.

1) Confirm repo state
- From repo root, run: `git status`
- Ensure working tree is clean or stash local edits.

2) Read context (5 minutes)
- `README.md` - quick project overview, GUI pointers, and CLI.
- `docs/ROADMAP.md` - Current capabilities, phase progress, milestones (see top section).
- `docs/setup/NEW_PC_SETUP.md` - Complete setup guide for deploying on a new machine.
- `docs/guides/DEVICE_INTEGRATION_GUIDE.md` - Primary architecture guide for device integration.
- `docs/schemas/WRAPPER_IO.md` - wrapper I/O contract (ping, status, shutdown).
- `docs/schemas/SEQUENCE_SCHEMA.md` - sequence/manifest schema.
- `docs/run_history/README.md` - canonical manifests for the latest hardware validation runs.

3) Verify local config
- Open `config/device_paths.yaml` and confirm per-device `repo`, `python`, `wrapper`, `mode` values for this machine.
- For hardware tests later, update `mode` and any `env` entries per device.

4) Quick smoke (CLI)
- Start wrappers (mock): `python src/supervisor_cli.py start all`
- Status check: `python src/supervisor_cli.py status`
- Dry-run baseline: `python src/run_cli.py run --plan examples/full_system_test.yaml --dry-run`
- Hardware rehearsal: `python src/run_cli.py run --plan examples/full_system_test_hw.yaml`
- Show last run manifest: `python src/run_cli.py show runs/<latest_run_dir>`
- Gamry wrapper health check after code changes: from Gamry repo run `py -3.7-32 scripts/goed_bridge.py --mock --once --log-dir logs`, then restart via supervisor so updated describe/schema are live.
- For Gamry CV/LSV testing use `examples/gamry_hardware_smoke.yaml` (0.5 V vertex, cycles per test). Review the generated `runs/<stamp>/manifest.json` after each hardware run.
- Between back-to-back Gamry runs, toggle the potentiostat to Cell OFF or run a short OCV so the stage starts from a neutral state.

5) GUI dashboard (Phase 7 focus)
- Launch v3: `python src/goed_gui_v3.py` (modular GUI with Array Mode fixes - RECOMMENDED)
- Launch v2: `python src/goed_gui_v2.py` (legacy monolithic GUI - for reference)
- Start All / Stop All / Ping All from toolbar
- Run Sequence (Live): select `examples/full_system_test_hw.yaml` or build sequence in Method Panel
- Gamry control tab features:
  1. Click "Start All Devices" (or start Gamry from toolbar dropdown).
  2. Navigate to "Gamry" tab in left panel.
  3. Choose technique (CV/LSV/CA/CP/OCV/EIS) and click **Run Technique**.
  4. Profile dialog appears (operator, sample_id, electrodes) - required before runs.
  5. Method Panel below allows building sequences: Add steps, then **Run Sequence**.
  6. Import/Export sequences as JSON files.
- Control panel is scrollable for smaller screens.

6) Hardware state & references
- Thorlabs camera remains hardware-only; confirm `config/device_paths.yaml` → `thorlabs.mode=hardware` and DLL path before running.
- Latest validated runs live under `runs/` (see `docs/run_history/README.md` for paths). Keep adding entries there after each milestone.
- Use the GUI quick action "Thorlabs: Capture Snapshot" after power cycles and before the full system plan.

7) Logs and artifacts
- Run outputs live under `runs/`. This folder is git-ignored; keep manifests for review as needed. Archive stale runs to `archive/` to keep the working set small.
- Acceptance test artifacts are git-ignored at `tests/acceptance_results.json`.
- For ad-hoc test artifacts that should live in git, use `tests/artifacts/` (small files only; clean up bulky data).
- Gamry clamp detection is enabled. If GOED reports a clamp, the CV already stopped and Cell OFF was issued-investigate the dummy cell/cabling before retrying.

8) Device Architecture (native branch - permanent)
 - **Status (2025-12-03)**: Phase 8 COMPLETE - Full process isolation with USB resilience
 - **Branch**: `native` — Primary development branch (all future work continues here)
 - **Note**: The `native` branch is the permanent main branch; no merge to `master` planned
 - **See**: `docs/guides/DEVICE_INTEGRATION_GUIDE.md` for architecture details
 - **See**: `docs/ROADMAP.md` Phase 8 for implementation milestones

 **Unified Device Registry Architecture (Section 9)**
  ```
  Panel  →  device.execute_async()  →  Callback  →  Signal  →  UI Update
                      ↓
              PIWrapperDevice / GamryDevice / ThorlabsWrapperDevice
                      ↓
              DeviceSupervisor (JSON IPC)
                      ↓
              Wrapper subprocess
  ```

 **All Panels Now Use device_registry Pattern:**
  - `ThorlabsControlPanelV2` → `ThorlabsWrapperDevice`
  - `PIControlPanel` → `PIWrapperDevice` (NEW)
  - `GamryControlPanel` → `GamryDevice`

 **PI XYZ Wrapper Options** (config/device_paths.yaml):
  - **Option A (External)**: Uses PI_XYZ repo's goed_bridge.py
  - **Option B (Internal)**: Uses GOED's scripts/pi_bridge.py + src/pi/ (RECOMMENDED)
  - Internal wrapper validated on hardware (2025-12-03)
  - Internal has more commands: move_absolute, park_all, run_sequence, cancel_sequence

 **Implementation Phases:**
  - **WP1 (Complete)**: Thorlabs wrapper JSON-only (no live view)
    - ✅ `scripts/thorlabs_bridge.py` - Uses GOED's `src/camera/` module
    - ✅ Commands: ping, status, shutdown, connect, disconnect, snapshot, set_exposure, set_gain, get_settings
    - ✅ `src/devices/thorlabs_wrapper_device.py` - Wrapper-based device
    - ✅ Validated: All 3 devices (Thorlabs, PI XYZ, Gamry) running without USB conflicts
  - **WP2 (Complete)**: Shared Memory live view + GUI responsiveness
    - ✅ `src/camera/shared_memory.py` - Lock-free SPSC ring buffer
    - ✅ Live view commands: start_live, stop_live with SharedMemory frame delivery
    - ✅ USB coordination: Thorlabs pauses during PI connect operations
    - ✅ Event logging system: `src/utils/event_logger.py`
    - ✅ GUI responsiveness: Tab switching works during PI XYZ moves
  - **WP3 (Complete)**: Integration & validation
    - ✅ USB coordination: Camera controls disabled during PI USB operations
    - ✅ Auto-exposure reduction for live view (20ms default)
    - ✅ Frame fetcher optimization (conditional sleep)
    - ✅ Live view stable during PI XYZ movements and Gamry measurements
    - ✅ Multi-device workflow validated (Thorlabs + PI XYZ + Gamry simultaneous)
    - ✅ Test artifacts: `tests/manual/test_wp3_integration.py`, `tests/manual/GUI_VALIDATION_WP3.md`
  - **Section 9 (Complete)**: Unified device_registry architecture
    - ✅ `src/devices/pi_wrapper_device.py` - PIWrapperDevice (new)
    - ✅ `src/gui/panels/pi_control_panel.py` - Migrated to device_registry pattern
    - ✅ `src/gui/panels/gamry_control_panel_v2.py` - Migrated to device_registry pattern
    - ✅ All panels use same communication pattern as ThorlabsControlPanelV2
    - ✅ PI XYZ and Gamry validated on hardware (2025-12-03)

 **Why Shared Memory for Thorlabs?**
  - Video frames: 1440×1080×3 @ 30 FPS = ~140 MB/s
  - stdin/stdout JSON max throughput: ~10 MB/s (would give ~2 FPS)
  - Shared memory: ~10 GB/s (zero-copy numpy access)

 **Known Issues (tracked for future optimization):**
  - **FPS gap**: Current ~8-10 FPS vs 30+ FPS in official Thorlabs software
    - Bottleneck likely in pylablib SDK's frame polling or camera configuration
    - Live view is stable; this is a performance optimization, not stability issue
    - Investigate: frame callbacks vs polling, camera buffer configuration

 **Resolved Issues:**
  - **USB resilience** (fixed 2025-12-03): Thorlabs camera no longer crashes during PI jog operations
    - Implemented adaptive polling backoff (10ms → 50ms → 100ms → 500ms) when frames stop
    - Fixed race condition where Start Live button was re-enabled during USB operations
    - Added stall detection in wrapper to recover from frozen streams
    - Live view now survives PI XYZ jog operations without crashing
  - **PI velocity control** (fixed 2025-12-05): GUI velocity spinbox now properly controls move speed
    - Root cause: Spinbox value was never sent to device; homing set velocity to 20 mm/s and it stayed there
    - Fix: Connected `spin_velocity.valueChanged` → `set_velocity` command with 300ms debounce
    - Velocity changes now appear in `logs/pi_bridge.log` and status label confirms

 **PI XYZ Sequence Integration (2025-12-04):**
  - **Status**: COMPLETE - Mixed sequences and single runs fully functional
  - **Completed**:
    - ✅ PI step dialogs: `src/widgets/pi_step_dialogs.py` (6 dialogs)
    - ✅ SequenceTableWidget: Multi-device menu (Gamry + PI XYZ steps)
    - ✅ Mixed sequence execution: `_run_mixed_sequence()` in goed_gui_v2.py
    - ✅ Pre-run validation: `src/sequence/sequence_validator.py`
    - ✅ Cross-thread signal for PI step completion
    - ✅ Sequence table display during mixed sequence runs
    - ✅ Post-sequence cleanup: `_finish_mixed_sequence()` properly resets state
    - ✅ Stop handling: `_on_command_interrupted_dispatcher()` handles mixed sequences
    - ✅ Single device runs work after mixed sequences (both Gamry and PI XYZ)
  - **Fixes Applied (2025-12-04)**:
    - **Post-sequence cleanup**: Added mixed sequence detection in interrupt handler
    - **Gamry fallback**: Panel checks device connection, falls back to supervisor path if disconnected
    - **PI panel status**: Added status label for visual feedback on operations
    - **PI move_absolute**: Fixed parameter names (`x_mm`→`x`, `y_mm`→`y`, `z_mm`→`z`)
    - **Connection checks**: Both panels validate device connection before executing commands
  - **Files Added**:
    - `src/widgets/pi_step_dialogs.py` - PI step configuration dialogs
    - `src/sequence/sequence_validator.py` - Pre-run validation for mixed sequences
  - **Files Modified**:
    - `src/goed_gui_v2.py` - Mixed sequence execution, cleanup fix
    - `src/pi_control_panel.py` - Status label, connection checks, parameter fix
    - `src/gamry_control_panel_v2.py` - Connection check with supervisor fallback

 **Mixed Sequence Export (2025-12-05):**
  - **Status**: COMPLETE - Unified folder structure and exports for mixed sequences
  - **Features**:
    - ✅ Shorter folder naming: `{operator}_mixed_{N}steps_{timestamp}`
    - ✅ Unified step numbering: PI steps get `StepNNN_PI-{action}.json` artifacts
    - ✅ GOED format manifest with all steps (Gamry + PI XYZ)
    - ✅ sequence-info.txt with device/action columns for mixed sequences
    - ✅ PNG plots generated for Gamry steps
  - **Output Structure**:
    ```
    GD_mixed_6steps_20251205_143000/
    ├── Step001_OCV.csv + .png      (Gamry)
    ├── Step002_CA.csv + .png       (Gamry)
    ├── Step003_PI-abs.json         (PI XYZ movement record)
    ├── Step004_CP.csv + .png       (Gamry)
    ├── Step005_PI-rel.json         (PI XYZ movement record)
    ├── Step006_CV_Cyc0001.csv +.png (Gamry)
    ├── manifest.json               (GOED format with all steps)
    └── sequence-info.txt           (human-readable summary)
    ```
  - **Files Modified**:
    - `src/goed_gui_v2.py` - `_write_mixed_sequence_manifest()`, `_write_pi_step_artifact()`, shorter naming
    - `src/utils/storage.py` - Support for GOED manifest format, PI step formatting

 **Future Enhancements:**
  - **Thorlabs sequence steps**: Add camera operations to sequence builder

 **Completed (Phase 8):**
  - ✅ Device Abstraction Layer (`src/devices/`)
  - ✅ Native camera module (`src/camera/`)
  - ✅ ThorlabsDevice (native, archived) - `src/devices/thorlabs_device.py`
  - ✅ Architecture analysis - IPC options evaluated, hybrid design selected
  - ✅ WP1: Thorlabs wrapper (JSON-only, process isolated)
  - ✅ WP2: SharedMemory live view + GUI responsiveness
  - ✅ WP3: Full multi-device integration validated
  - ✅ PI XYZ wrapper consolidated into GOED (scripts/pi_bridge.py)
  - ✅ USB coordination between PI XYZ and Thorlabs (controls disabled during USB ops)
  - ✅ Event logging for multi-device debugging
  - ✅ USB resilience: Adaptive polling backoff prevents Thorlabs SDK crashes during PI jogs
  - ✅ Legacy `thorlabs_control_panel.py` archived to `archive/old_control_panels/`

 **Key Files:**
  - `scripts/thorlabs_bridge.py` - Thorlabs wrapper (WP1+WP2+WP3)
  - `scripts/pi_bridge.py` - PI XYZ internal wrapper (Phase 3 consolidation)
  - `scripts/perimax_bridge.py` - Perimax pump wrapper
  - `src/devices/thorlabs_wrapper_device.py` - Wrapper-based ThorlabsDevice with live view
  - `src/devices/pi_wrapper_device.py` - Wrapper-based PIDevice (Section 9)
  - `src/devices/gamry_device.py` - Wrapper-based GamryDevice
  - `src/devices/perimax_wrapper_device.py` - Wrapper-based PerimaxDevice
  - `src/camera/shared_memory.py` - SharedMemory ring buffer for frame streaming
  - `src/camera/controller.py` - CameraController with optimized frame fetcher
  - `src/camera/` - CameraController, adapter, models (used by wrapper)
  - `src/pi/` - PI control module (manager, controller, models, errors)
  - `src/utils/event_logger.py` - Centralized event logging
  - `src/gui/panels/pi_control_panel.py` - PI panel with device_registry (Section 9)
  - `src/gui/panels/gamry_control_panel_v2.py` - Gamry panel with device_registry (Section 9)
  - `src/gui/panels/thorlabs_control_panel_v2.py` - Thorlabs panel with device_registry
  - `src/gui/panels/perimax_control_panel.py` - Perimax panel
  - `src/entrypoints/goed_gui_v3.py` - Main GUI (launcher: `src/goed_gui_v3.py`)
  - `src/supervisor/device_supervisor.py` - Device lifecycle management
  - `src/supervisor/supervisor_service.py` - QThread supervisor wrapper
  - `src/sequence/sequence_runner.py` - Sequence execution engine
  - `src/sequence/technique_schemas.py` - Technique parameter schemas
  - `config/device_paths.yaml` - Wrapper configurations (external/internal PI options)
  - `docs/schemas/WRAPPER_IO.md` - JSON protocol specification

 **Testing Multi-Device:**
  ```powershell
  # Launch GUI (v3 is the primary version)
  python src/goed_gui_v3.py

  # Test flow:
  # 1. Start All Devices from toolbar
  # 2. Connect Thorlabs and start live view
  # 3. Connect PI XYZ (live view auto-pauses/resumes)
  # 4. Jog PI XYZ while checking Thorlabs tab - should switch immediately
  ```

 **⚠️ IMPORTANT**: After modifying wrapper scripts, restart the wrapper process for changes to take effect.
- Keep wrappers stdout JSON-only; route hardware SDK logs to files/stderr.
- Manual tests live under `tests/manual/`.

9) Safety and conventions
- Stdout discipline for wrappers: JSON only; use stderr/log files for diagnostics.
- Avoid shell parsing; launch subprocesses with arg arrays (no `shell=True`).
- Do not commit machine-specific files (see `.gitignore`).

**PI XYZ Speed Configuration:**
- **Homing speed**: Controllers may default ref speed SPA 0x63/0x42 to 0.05 mm/s. GOED sets these to 20 mm/s + accel 200 mm/s² before each homing. If homing is slow, check `logs/pi_bridge.log` for SPA values or run `python scripts/pi_set_refspeed.py` (no motion) to confirm.
- **Move velocity**: User velocity from GUI spinbox is now applied via `set_velocity` command. Changes are debounced (300ms) to avoid flooding during spinbox drag. Velocity is clamped to max 20 mm/s by controller.
- **After homing**: Axes default to max velocity (20 mm/s). Change the GUI spinbox to set slower speeds for precision work.
- **Debugging velocity issues**: Check `logs/pi_bridge.log` for `set_velocity` entries. If velocity seems stuck, verify the command is being sent and the response is `ok: true`.

10) Gamry Single Run Fix (reliability branch - 2025-12-09)
 - **Status**: COMPLETE - Single runs now have full feature parity with sequences
 - **Branch**: `reliability` — Reliability improvements branch

 **Problem Solved:**
  - Single Gamry technique runs (Run Technique button) were missing:
    - Real-time plotting during acquisition
    - File export (CSV artifacts)
    - PNG plot generation
    - GUI logging
  - Root cause: `GamryDevice.execute_async()` bypassed all CommandDispatcher infrastructure
  - Sequences worked because they used `CommandDispatcher` directly

 **Solution:**
  - Single runs now route through `execute_action()` → `CommandDispatcher` (same as sequences)
  - `GamryDevice.execute_async()` reserved for control commands (connect, disconnect, pause, stop)
  - Single runs skip `sequence-info.txt` export (only sequences generate this)

 **Additional Fixes:**
  - **Wrapper protocol**: Fixed `GamryDevice` to use correct action names:
    - `"action": "start"` → `"action": "run_cv"` (and other techniques)
    - `"action": "stop"` → `"action": "stop_task"`
  - **Missing capabilities**: Added `run_ocv`, `pause_task`, `continue_task` to GamryDevice
  - **Dynamic timeouts**: Timeout now calculated from technique parameters:
    - CA, CP, OCV: `duration_s + 60s buffer` (supports multi-hour experiments)
    - CV, LSV: Estimated from voltage range, scan rate, and cycles
    - EIS: Estimated from frequency range and points per decade
    - Fallback: `DEFAULT_TIMEOUTS` from `action_mapper.py`

 **Files Modified:**
  - `src/devices/gamry_device.py` - Wrapper protocol fixes, added pause/continue commands
  - `src/gamry_control_panel_v2.py` - Route single runs through CommandDispatcher
  - `src/goed_gui_v2.py` - `_calculate_technique_timeout()`, skip sequence-info for single runs

 **Testing Single Runs:**
  1. Launch GUI: `python src/goed_gui_v2.py`
  2. Start Gamry wrapper (Start All or Gamry-specific)
  3. Click Connect in Gamry tab
  4. Select technique (CV, OCV, etc.) and set parameters
  5. Fill in Profile dialog (operator, sample_id)
  6. Click "Run Technique"
  7. **Expected**: Real-time plot updates, CSV/PNG in runs/ folder, execution log entries

11) Reliability Framework (reliability branch - 2025-12-08, UPDATED 2026-01-08)
 - **Status**: Phase A+B+C+D+E+F+G+H COMPLETE - Full reliability framework with USB disconnect detection

 **Device Connection Stability (2025-12-08):**
  - **PI XYZ**: Fixed ping handler resetting `connected=False` on transient errors
  - **PI/Thorlabs**: Added PID tracking to detect bridge restarts and auto-reconnect
    - Tracks `_connected_bridge_pid` when connect succeeds
    - If PID changes (auto-restart), automatically re-sends connect command
  - **Gamry**: Fixed enum cache not clearing after connect (showed REF620 enums for IFC1010)
    - Clears `_cached_enums = None` after successful connect in goed_bridge.py
  - **Gamry**: Added friendly model names (PC61010 → Interface 1010E)

 **Thorlabs Camera Auto-Recovery (2025-12-08):**
  - **Problem**: Thorlabs SDK can hang, causing FPS to drop to 0 with no recovery
  - **Solution**: Two-tier automatic recovery system
  - **Stall Detection** (5 second threshold):
    - Frame reader tracks `_last_frame_time` for each frame received
    - Every second, checks if no frames for > 5 seconds
    - Up to 3 consecutive recovery attempts before giving up
  - **Tier 1 - Soft Recovery** (10s timeout):
    - Sends `start_live` to bridge (which has its own camera recovery)
    - Bridge detects stall and attempts camera reconnect
  - **Tier 2 - Force Restart** (if Tier 1 times out):
    - Kills the hung bridge process forcefully
    - Waits 3s for USB to settle
    - Restarts bridge subprocess
    - Reconnects to camera and restarts live view
  - **Files Modified**:
    - `src/devices/thorlabs_wrapper_device.py` - `_trigger_stall_recovery()`, `_force_restart_bridge()`
    - `scripts/thorlabs_bridge.py` - `_attempt_camera_recovery()` (existing)
  - **Log Messages**:
    - `"Thorlabs: Stream stalled! No frames for X.Xs"` - Stall detected
    - `"Thorlabs: Bridge not responding - will force restart"` - Tier 2 triggered
    - `"Thorlabs: Bridge restart recovery successful!"` - Recovery complete

 **⚠️ Known Issue - Thorlabs Camera Stability (TODO):**
  - **Status**: PARTIALLY FIXED - Recovery logic works but camera may not reconnect
  - **Observed Behavior** (2025-12-08):
    - Camera ran for ~3651 frames (~12 minutes at 5 FPS) before stalling
    - Auto-recovery triggered correctly (stall detection → soft recovery timeout → force restart)
    - Bridge process killed and restarted successfully
    - **BUT camera reconnect failed** after bridge restart
  - **Root Cause**: Thorlabs SDK/USB driver instability
    - SDK can hang internally (blocking calls never return)
    - After force-killing process, camera may need longer USB settle time
    - May require physical USB reconnect in severe cases
  - **Future Work (TODO)**:
    - [ ] Increase USB settle time (currently 3s, try 5-10s)
    - [ ] Add retry loop for camera reconnect after bridge restart
    - [ ] Investigate if SDK cleanup is incomplete before process kill
    - [ ] Consider USB hub power-cycle as last resort recovery
    - [ ] Profile SDK to identify which call hangs (read_newest_image? start_acquisition?)
    - [ ] Test with different USB ports/hubs for stability comparison

 **Modules Added:**
  - `src/auto_restart_controller.py` - Bridges supervisor heartbeat to RestartManager
  - `src/error_classifier.py` - Classifies errors by severity (transient/recoverable/permanent)
  - `src/utils/retry.py` - @with_retry decorator, RetryContext, RecoveryHelper
  - `src/utils/correlation.py` - Thread-safe correlation IDs for tracing
  - `src/utils/structured_logger.py` - JSON logging with rotation

 **Auto-Restart Architecture:**
  ```
  DeviceSupervisor._heartbeat_loop()
      → detects consecutive_misses >= 3
      → calls on_unhealthy callback
      → AutoRestartController._handle_unhealthy()
      → waits backoff delay (2s, 5s, 15s, 30s)
      → supervisor.stop() + supervisor.start()
      → emits on_restart_completed for GUI
  ```

 **Error Classification:**
  - TRANSIENT: USB busy, timeout → Retry with short backoff (0.5-4s)
  - RECOVERABLE: Device not found, servo off → Retry after device reset (2-30s)
  - PERMANENT: Cell not connected, limit switch → Stop, notify user
  - Gamry requires operator confirmation for safety

 **PI Recovery:**
  - `scripts/pi_bridge.py` now has `recover` command and `_attempt_pi_recovery()` method
  - Exponential backoff (2s, 4s, 8s) for USB recovery

 **Stress Testing:**
  - `tests/stress/stress_test_framework.py` - StressTestRunner with sustained ping and chaos testing
  - `tests/stress/run_soak_test.py` - CLI for soak tests
  - Quick validation: `python tests/stress/run_soak_test.py --quick`
  - 1-hour soak: `python tests/stress/run_soak_test.py --hours 1`
  - 24-hour with chaos: `python tests/stress/run_soak_test.py --hours 24 --chaos`

 **Structured Logging:**
  - JSON logs: `logs/goed_structured.jsonl` (10MB rotation, 5 backups)
  - Correlation IDs trace operations across devices and threads
  - Use `CorrelationContext("seq_123")` to group related logs

 **Test Coverage:**
  - 168 unit tests covering all reliability modules:
    - 35 tests: auto_restart with heartbeat enhancement (test_auto_restart.py)
    - 21 tests: circuit breaker pattern (test_circuit_breaker.py)
    - 32 tests: V3 executor unit tests (test_executors.py)
    - 17 tests: multi-device fault scenarios (test_multi_device_fault.py)
    - 63 tests: error_classifier, retry, correlation, structured_logger, stress_framework
  - Run all reliability tests: `python -m unittest tests.test_auto_restart tests.test_error_classifier tests.test_retry tests.test_correlation tests.test_structured_logger tests.test_stress_framework tests.test_circuit_breaker tests.test_executors tests.test_multi_device_fault`

 **Phase A: Silent Failure Fixes (2025-12-16):**
  - **Problem**: 8 CRITICAL silent failure locations where `except: pass` hid errors
  - **Solution**: Replace with specific exception handling and proper logging
  - **Files Fixed**:
    - `src/goed_gui_v3.py` (4 locations) - Manifest refresh, device connection checks, state callbacks
    - `src/command_dispatcher.py` (1 location) - Temp file cleanup logging
    - `src/devices/thread_safe_device.py` (1 location) - Device status retrieval with `status_error` field
  - **Pattern Applied**:
    ```python
    # BEFORE (bad)
    except Exception:
        pass
    # AFTER (good)
    except SpecificException as e:
        logger.warning(f"Non-critical error: {e}")
    ```

 **Phase B: Circuit Breaker Pattern (2025-12-16):**
  - **Problem**: No protection against cascading failures in sequences
  - **Solution**: Circuit breaker that opens after N consecutive failures
  - **New Module**: `src/utils/circuit_breaker.py`
    - `CircuitBreaker` class with CLOSED/OPEN/HALF_OPEN states
    - `CircuitBreakerRegistry` for managing multiple breakers
    - Thread-safe with statistics tracking
  - **Configuration**: 5 consecutive failures triggers auto-stop
  - **Integration**:
    - `src/executors/array_mode_executor.py` - Stops array after point failures
    - `src/executors/mixed_sequence_executor.py` - Stops sequence after step failures
  - **Behavior**:
    - Each sequence creates a fresh circuit breaker
    - Successes reset consecutive failure count
    - 5 failures → circuit opens → sequence auto-stops with user notification
    - 300s reset timeout for recovery attempts
  - **Unit Tests**: `tests/test_circuit_breaker.py` (21 tests)
    - Run: `python -m unittest tests.test_circuit_breaker`

 **Phase C: Command Timeout Watchdog (2025-12-16):**
  - **Problem**: Commands could hang indefinitely if wrapper/device becomes unresponsive
  - **Solution**: QTimer-based watchdog in CommandDispatcher
  - **File Modified**: `src/command_dispatcher.py`
  - **Implementation**:
    - Watchdog timer checks every 5 seconds if command exceeded timeout
    - Total timeout = step timeout + 30s buffer for overhead
    - On timeout: graceful stop (2s), then terminate if needed
    - Emits `command_failed` signal with timeout error message
    - Event logging tracks timeout events for diagnostics
  - **New Methods**:
    - `_check_timeout()` - Periodic watchdog callback
    - `_force_timeout()` - Force-stop hung commands
    - `_stop_watchdog()` - Cleanup timer state
  - **Behavior**:
    - Watchdog starts when `execute_command()` dispatches
    - Watchdog stops on command completion/failure
    - If timeout exceeded: logs warning, stops worker, emits failure

 **Phase D: V3 Executor Unit Tests (2025-12-16):**
  - **Problem**: V3 executors had 0% test coverage (916+ lines)
  - **Solution**: Comprehensive unit tests with mocks for hardware isolation
  - **New File**: `tests/test_executors.py` (32 tests)
  - **Test Coverage**:
    - BaseSequenceExecutor: Session info generation, running state, step state updates
    - GamrySequenceExecutor: Start validation, stop flags, technique mapping, artifact extraction
    - MixedSequenceExecutor: Mixed device steps, circuit breaker integration
    - ArrayModeExecutor: Config validation, circuit breaker, pause/resume state
  - **Mock Architecture**:
    - MockDispatcher: Simulates CommandDispatcher without hardware
    - MockSequenceTable: Captures UI state updates
    - MockDevice: Simulates device callbacks
  - **Run Tests**: `python -m unittest tests.test_executors`
  - **Combined with circuit breaker**: `python -m unittest tests.test_circuit_breaker tests.test_executors` (53 tests)

 **Phase E: Multi-Device Fault Integration Tests (2025-12-16):**
  - **Problem**: No integration tests for fault handling across device boundaries
  - **Solution**: Comprehensive test suite for multi-device fault scenarios
  - **New File**: `tests/test_multi_device_fault.py` (17 tests)
  - **Test Coverage**:
    - Mixed sequence device faults (Gamry fails during PI sequence, PI disconnects)
    - Array mode fault isolation (circuit breaker stops cascading failures)
    - Cross-device isolation (errors in one device don't corrupt another)
    - Recovery scenarios (circuit breaker HALF_OPEN recovery)
    - Concurrent failures (multiple circuit breakers operating independently)
    - Error classification validation (TRANSIENT/RECOVERABLE/PERMANENT)
  - **Test Classes**:
    - TestMixedSequenceDeviceFaults: Gamry and PI failure handling
    - TestMixedSequenceRecovery: Success resets failure counts
    - TestArrayModeFaultIsolation: Point failures don't crash executor
    - TestCrossDeviceIsolation: Device errors are isolated
    - TestRecoveryScenarios: Circuit breaker state transitions
    - TestConcurrentFailures: Registry manages multiple breakers
    - TestErrorClassification: Error severity detection
  - **Run Tests**: `python -m unittest tests.test_multi_device_fault`

 **Phase F: Enhanced Stress Testing (2025-12-16):**
  - **Problem**: Basic stress test framework lacked realistic multi-device scenarios
  - **Solution**: Extended framework with 4 new test types
  - **File Enhanced**: `tests/stress/stress_test_framework.py`
  - **New Test Classes**:
    - `MixedLoadTest` - Concurrent Gamry + PI + Thorlabs operations
      - Runs CV cycles, PI moves, and Thorlabs snapshots simultaneously
      - Configurable intervals and duration
    - `ExtendedChaosTest` - Simultaneous multi-device failures
      - Kills up to N devices at once
      - Validates recovery across all killed devices
      - Excludes Gamry for safety by default
    - `ResourceMonitor` - Memory/handle leak detection
      - Tracks process memory growth over time
      - Detects handle leaks (Windows)
      - Alerts when thresholds exceeded
    - `DataIntegrityTest` - File creation and checksum validation
      - Runs operations and validates output files
      - Checks file sizes and MD5 checksums
      - Detects truncation or corruption
  - **Convenience Functions**:
    - `run_mixed_load_test(duration_minutes=30)` - Quick mixed load test
    - `run_extended_chaos_test(duration_minutes=30, simultaneous=2)` - Chaos test
    - `run_resource_monitor(duration_minutes=60)` - Leak detection
    - `run_data_integrity_test(duration_minutes=30)` - Data validation
  - **Run All Tests**: `python -m unittest tests.test_circuit_breaker tests.test_executors tests.test_multi_device_fault` (70 tests)

 **Phase G: Heartbeat Enhancement (2026-01-07):**
  - **Problem**: Fixed heartbeat interval, no early warning before UNHEALTHY, no latency trending
  - **Solution**: Enhanced heartbeat with latency tracking, health score, and degradation detection
  - **Files Modified**:
    - `src/supervisor/device_supervisor.py` - Latency trending, health score, on_degraded callback
    - `src/auto_restart_controller.py` - Wire on_device_degraded callback
    - `tests/test_auto_restart.py` - 19 new tests (35 total)
  - **New Features**:
    - **Latency Trending**: Tracks last 10 ping latencies, computes median baseline after 5 samples
    - **Health Score**: 0.0-1.0 weighted metric (success rate 40%, latency 30%, misses 30%)
    - **Degradation Detection**: Emits `on_degraded` when latency exceeds 3× baseline for 2+ pings
    - **Per-Device Config**: `heartbeat_interval_s` and `heartbeat_miss_threshold` in device_paths.yaml
  - **New get_status_dict() Fields**:
    - `health_score`: Current health (0.0-1.0)
    - `latency_baseline_ms`: Learned baseline latency
    - `heartbeat_interval_s`: Device-specific interval
    - `miss_threshold`: Device-specific miss threshold
    - `consecutive_degraded`: Count of consecutive high-latency pings
  - **Optional Config** (add to device_paths.yaml per device):
    ```yaml
    pi_xyz:
      heartbeat_interval_s: 3    # Faster for responsive device
      heartbeat_miss_threshold: 2
    thorlabs:
      heartbeat_interval_s: 5
      heartbeat_miss_threshold: 4  # More tolerant for camera
    ```
  - **Validation**: 168 tests pass, validated with 3-point array mode hardware run

 **Phase H: USB Disconnect Detection (2026-01-08):**
  - **Problem**: USB disconnection during measurements not detected until technique timeout (60-120s)
  - **Solution**: Multi-layer detection with immediate user notification
  - **Files Modified**:
    - `src/supervisor/device_supervisor.py` - Heartbeat pings during busy state, hardware error detection from task_error
    - `src/auto_restart_controller.py` - Wire on_hardware_disconnect callback
    - `src/supervisor_service.py` - hardware_disconnected signal
    - `src/goed_gui_v3.py` - Critical error popup dialog
    - `src/devices/thread_safe_device.py` - Circuit breaker integration
    - `src/widgets/hardware_status_bar.py` - Circuit state indicator (hidden when healthy)
  - **Detection Mechanisms**:
    - **Heartbeat during busy**: Pings wrapper every 5s even during measurements, checks `hardware_ok`
    - **Task error detection**: Detects hardware errors from technique failures ("Unable to initialize", etc.)
    - **Immediate notification**: Critical error popup when hardware disconnect detected
  - **Circuit Breaker Integration**:
    - Circuit breaker at device layer (`thread_safe_device.py`)
    - Visual indicator in status bar (amber for HALF_OPEN, red for OPEN)
    - 5 consecutive failures opens circuit, 300s timeout for recovery
  - **Limitation**: Gamry wrapper's `handle_ping()` checks cached state, not actual USB
    - True immediate detection requires Gamry wrapper update in external repo
    - Current detection: when next technique fails to start (~10s after disconnect)
  - **User Experience**:
    - Error popup with device name, error message, and recovery instructions
    - Log entry: `"⛔ gamry: HARDWARE DISCONNECTED - ..."`
    - Status bar shows circuit state if degraded

12) Array Mode (reliability branch - 2025-12-11, FIXED 2025-12-12)
 - **Status**: COMPLETE - Multi-point execution fully functional in v3 (see Section 13)

 **What Array Mode Does:**
  - Run a Gamry sequence (OCV → CA → CP → LSV → CV → EIS) at each of multiple XYZ positions
  - Move to position → settle → execute all Gamry steps → move to next position → repeat
  - Progress tracking per position and per step
  - Pause/Resume/Stop controls during execution

 **Implementation:**
  - `src/models/array_models.py` - ArrayPosition, ArraySequenceConfig, ArrayRunPhase, ArrayRunState
  - `src/utils/array_io.py` - Position import/export (CSV/JSON), validation, travel limits
  - `src/widgets/array_mode_widget.py` - Position table, settle time, progress display, run controls
  - `src/goed_gui_v2.py` - Array sequence execution, state machine, phase transitions

 **UI Features:**
  - Sequence Manager widget with Mixed Mode / Array Mode toggle
  - Position table with X/Y/Z/Label columns + status indicator
  - Import/Export buttons for positions (CSV or JSON)
  - Settle time configuration (seconds to wait after each move)
  - Progress bar and Point/Step counters
  - Run/Stop/Stop Now/Pause/Resume buttons

 **Device Connection Detection:**
  - Array Mode requires both PI XYZ and Gamry connected
  - Run button disabled with "PI XYZ not connected" / "Gamry not connected" messages
  - Connection status updated via device state change callbacks
  - Uses `device.is_connected()` which checks state in (READY, BUSY)

 **Files Added:**
  - `src/models/__init__.py` - Models package init
  - `src/models/array_models.py` - Array mode data models
  - `src/utils/array_io.py` - Position I/O and validation utilities

 **Files Modified:**
  - `src/goed_gui_v2.py` - Array execution, device state callbacks, connection status updates
  - `src/sequence_validator.py` - Added `validate_array_config()` function
  - `src/utils/__init__.py` - Export array_io functions
 - `src/utils/storage.py` - Added `write_array_sequence_info()`
 - `src/widgets/__init__.py` - Export ArrayModeWidget

 **Array Exports (2025-12-12 update)**
  - Per-point folders now use short names `P01`, `P02`, … for Windows path safety
  - Each point folder contains full Gamry exports: `manifest.json`, CSVs, PNG plots, and `sequence-info.txt`
  - The array-level `manifest.json` includes per-point folder names, statuses, and artifact lists

13) UI Theme Isolation (v3)
 - Appearance-only hook lives in `src/ui/theme.py` + `src/styles/app.qss`
 - Loaded via `create_application()` in `src/app/bootstrap.py`; QSS is empty by default (no layout change)
 - Adjust palette/QSS there if visual tweaks are needed without touching logic

 **Crash Fix (2025-12-11):**
  - **Problem**: GUI crashed (0xC0000409 STACK_BUFFER_OVERRUN, 0xC0000005 ACCESS_VIOLATION) during Array Mode
  - **Root Cause**: Reentrancy - `_on_array_gamry_step_completed` immediately dispatched next step while CommandDispatcher was still cleaning up, clobbering the new worker/temp file
  - **Solution**: QTimer.singleShot(100ms) defer pattern for step chaining (matches Gamry-only/mixed sequences)
  - **Additional Fixes**:
    - Dynamic timeout calculation for Array Mode (was using default 60s, now uses `_calculate_technique_timeout`)
    - Minimum 60s timeout clamp to prevent underestimated timeouts
    - Failure gate: Auto-pause before PI move if Gamry step failed (prevents crash after technique error)
    - Retry counter reset at step start (prevents carryover between steps)
    - Stop/pause check in defer window
    - Diagnostic logging for PI move path
  - **Validated**: 5-point × 6-technique array completed successfully (logs/goed_events_20251211_101520.log)

 **Baseline/Context Fix (2025-12-11):**
  - **Problem**: All Array Mode Gamry steps failed with `run_ocv validation failed: Unknown parameter: auto_range`
  - **Root Cause**: Array Mode flattened PStat context into params root level (`params = {**baseline, **params}`)
    - Gamry wrapper expects PStat settings nested under `params['context']`
    - Mixed/pure sequences used correct pattern; Array Mode had incorrect merge
  - **Solution**: Match exact pattern from mixed/pure sequences:
    ```python
    context_overrides = step.get('context_overrides', {})
    if self._array_baseline or context_overrides:
        resolved_context = {}
        if self._array_baseline:
            resolved_context.update(self._array_baseline)
        if context_overrides:
            resolved_context.update(context_overrides)  # Overrides win
        params['context'] = resolved_context
    ```
  - **Validated**: 5-point × 5-technique array completed (logs/goed_events_20251211_122404.log)

 **Health Check False Positive Fix (2025-12-11):**
  - **Problem**: "Device 'gamry' has become unhealthy" popup during normal Gamry operation
  - **Root Cause**: DeviceSupervisor heartbeat loop pinged Gamry during async techniques
    - Long-running techniques (30+ seconds) caused consecutive heartbeat misses
    - 3 misses triggered false unhealthy detection
  - **Solution**: Added busy flag to skip heartbeats during CommandDispatcher execution
    - `DeviceSupervisor.busy` flag (default False)
    - Heartbeat loop checks `if self.busy: continue` (skips ping)
    - `SupervisorService.mark_device_busy/idle()` propagates to supervisor
  - **Files Modified**:
    - `src/supervisor/device_supervisor.py` - Added `self.busy` flag, heartbeat loop skip
    - `src/supervisor_service.py` - Added `mark_device_busy()` / `mark_device_idle()`
  - **Validated**: Long CA/CV runs no longer trigger false unhealthy popups

 **Multi-Point Transition Bug - RESOLVED (2025-12-12)**
  - **Previous symptom**: Array Mode completed P01 steps but froze/crashed transitioning to P02
  - **Root cause found**: v2's monolithic architecture had callback/thread context issues
  - **Resolution**: v3 modular refactoring with proper executor pattern (see Section 13)

 **Testing Array Mode:**
  1. Launch GUI: `python src/goed_gui_v3.py` (new modular version)
  2. Connect PI XYZ and Gamry devices
  3. Switch to "Array Mode" in Sequence Manager
  4. Import positions or add manually (CSV: X,Y,Z,Label columns)
  5. Build Gamry sequence in Mixed Mode (OCV, CA, etc.)
  6. Switch back to Array Mode and click Run
  7. Monitor progress: Point N/M, Step X/Y counters
  8. If step fails: Array auto-pauses, check Gamry connection before Resume

13) V3 Modular Refactoring (reliability branch - 2025-12-12)
 - **Status**: COMPLETE - Multi-point Array Mode fully functional
 - **See**: `docs/V3_MODULAR_REFACTORING.md` for detailed extraction plan

 **Why Modular Refactoring:**
  - `goed_gui_v2.py` grew to ~5236 lines (monolithic, hard to maintain)
  - Callback/thread context issues in Array Mode caused crashes
  - Need separation of concerns for testability and maintainability

 **New Architecture:**
  ```
  goed_gui_v3.py (main window, ~2100 lines)
      ├── src/executors/
      │   ├── base_executor.py         - Common executor interface
      │   ├── gamry_sequence_executor.py - Pure Gamry sequences
      │   ├── mixed_sequence_executor.py - Mixed device sequences
      │   └── array_mode_executor.py   - Array Mode state machine
      ├── src/controllers/
      │   ├── device_actions.py        - Device action handlers
      │   └── gamry_controls.py        - Gamry-specific controls
      ├── src/widgets/
      │   ├── log_widget.py            - Execution log panel
      │   └── sequence_table_widget.py - Sequence table
      ├── src/utils/
      │   ├── export_helpers.py        - Manifest/export generation
      │   └── gamry_param_normalizer.py - Parameter normalization
      └── src/app/
          └── bootstrap.py             - Application initialization
  ```

 **Key Fixes in v3:**
  - **Array Mode dispatcher routing**: Fixed legacy v2 attribute checks (`_gamry_sequence_steps`)
    - Changed to use `executor.is_running()` for proper state detection
  - **Explicit `_array_run_active` flag**: v3 uses explicit flag like v2 pattern
  - **Computed property fix**: `ArrayRunState.completed_points` is read-only computed property
    - Removed invalid assignment; setting `point_statuses` auto-updates count
  - **Stop/Pause/Resume controls**: Fully implemented with device stop commands
    - `stop_now()` sends explicit `stop_task` to Gamry, `stop` to PI
  - **task_error callback**: Fixed task_id extraction for immediate failure handling
    - Was checking `details.task_id`, but task_error has it in `error.task_id`
  - **Context preservation**: Fixed `normalize_gamry_params()` stripping `context` key
    - Root cause of CV clamping at Point 2 (potentiostat settings drift)

 **Files Added:**
  - `src/executors/` - Executor state machines (4 files)
  - `src/controllers/` - Action handlers (3 files)
  - `src/widgets/log_widget.py` - Log panel widget
  - `src/widgets/sequence_table_widget.py` - Sequence table widget
  - `src/utils/export_helpers.py` - Export utilities
  - `src/utils/gamry_param_normalizer.py` - Parameter normalization
  - `src/app/bootstrap.py` - App initialization
  - `src/goed_gui_v3.py` - New modular main window

 **Files Modified:**
  - `src/sequence/sequence_runner.py` - task_error callback task_id fix

 **Testing v3:**
  ```powershell
  # Launch v3 GUI
  python src/goed_gui_v3.py

  # Test Array Mode:
  # 1. Start All Devices
  # 2. Connect PI XYZ and Gamry
  # 3. Add positions in Array Mode tab
  # 4. Build sequence (OCV, CA, CP, LSV, CV, EIS)
  # 5. Run - should complete all points without clamping errors
  ```

 **Migration Path:**
  - v2 (`goed_gui_v2.py`) remains for reference
  - v3 (`goed_gui_v3.py`) is the new primary GUI
  - `launch_gui.bat` now uses v3 (updated 2025-12-16)

14) Hardware Status Bar (reliability branch - 2025-12-17)
 - **Status**: COMPLETE - Real-time device status in toolbar

 **What's New:**
  - Modular `HardwareStatusBar` widget (`src/widgets/hardware_status_bar.py`)
  - Real-time status updates via 2-second polling from SupervisorService
  - LED indicators: Green (connected), Yellow (wrapper ready), Red (stopped)
  - Summary text: "3/3 ready" or "2/3 connected"
  - Connection change signals for device state tracking

 **Architecture:**
  ```
  SupervisorService (QThread)
      ├── QTimer (2s interval, Qt.DirectConnection)
      │   └── _emit_status() → status_updated signal
      └── status_updated → GOEDMainWindowV3._on_status_updated (cross-thread)
                              └── HardwareStatusBar.update_status()
  ```

 **Qt Signal-Slot Fix:**
  - **Problem**: QTimer in worker thread wasn't firing due to Qt thread affinity
  - **Root Cause**: QThread object lives in creator thread, but timer in worker thread
  - **Fix**: Use `Qt.DirectConnection` for timer timeout → ensures slot runs in worker thread
  - **File Modified**: `src/supervisor_service.py` line 106

 **Status Handler Simplification:**
  - **Problem**: Hardware probes (`measure_v()`, `get_settings()`) in status handlers could interfere with running techniques
  - **Fix**: Removed hardware probing from all wrapper status handlers
  - **Rationale**: USB disconnection is detected when actual commands fail; status checks must never interfere with electrochemistry
  - **Files Modified**:
    - `Gamry/scripts/goed_bridge.py` - Removed `measure_v()` probe
    - `scripts/pi_bridge.py` - Simplified to cached state only
    - `scripts/thorlabs_bridge.py` - Simplified to cached state only

 **Busy Device Handling:**
  - `mark_device_busy()` / `mark_device_idle()` in SupervisorService
  - Status polls skip detailed requests for busy devices
  - Prevents status commands from blocking during techniques

 **Files Added:**
  - `src/widgets/hardware_status_bar.py` - New modular status bar widget

 **Files Modified:**
  - `src/supervisor_service.py` - Qt.DirectConnection fix, busy device logging
  - `src/goed_gui_v3.py` - Integrated HardwareStatusBar, simplified toolbar
  - `src/widgets/__init__.py` - Export HardwareStatusBar

 **Testing:**
  1. Launch GUI: `python src/goed_gui_v3.py`
  2. Observe toolbar shows "Initializing..." briefly, then "3/3 ready"
  3. Start devices - LEDs turn green for connected devices
  4. Run Array Mode sequence - status bar should NOT interfere with Gamry techniques

15) EIS PNG Export Fix (reliability branch - 2025-12-18)
 - **Status**: COMPLETE - EIS 3-panel PNG generation restored for all sequence types

 **Problem Solved:**
  - EIS steps in sequences (pure Gamry, mixed, array) were not generating PNG plots
  - Single EIS runs still worked; only sequence runs were affected
  - PNG file like `Step001_EIS.png` was missing after sequence completion

 **Root Cause:**
  - Silent `Path(art).exists()` checks were dropping artifacts when file path checks failed
  - Two locations had this issue:
    1. `_extract_artifacts()` in executors - dropped artifacts if exists() returned False
    2. `generate_sequence_exports()` - filtered out CSV files if exists() returned False
  - Path normalization issues on Windows (forward vs backslashes in JSON manifest) caused valid paths to fail exists() checks

 **Solution:**
  - Modified artifact extraction to include all artifacts even if exists() check fails
  - Added logging for missing artifacts instead of silent dropping
  - Added fallback path lookup in session folder for PNG generation
  - Normalize paths using `Path.resolve()` when files exist

 **Files Modified:**
  - `src/executors/gamry_sequence_executor.py` - `_extract_artifacts()` no longer drops artifacts silently
  - `src/executors/mixed_sequence_executor.py` - Same fix
  - `src/utils/export_helpers.py` - Two fixes:
    - `extract_artifacts_from_result()` includes all artifacts with warnings
    - `generate_sequence_exports()` tries alternate path in session folder

 **Testing:**
  - 32/32 executor unit tests pass: `python -m pytest tests/test_executors.py`
  - Manual validation: Run EIS in sequence, verify `Step001_EIS.png` generated

16) Thorlabs False "Connected" State Fix (reliability branch - 2025-12-18)
 - **Status**: COMPLETE - Thorlabs now correctly shows "Disconnected" until user clicks Connect

 **Problem Solved:**
  - After GUI launch, Thorlabs panel showed "Connected" without user clicking Connect
  - Clicking "Start Live" or "Snapshot" failed with "Camera not connected - call connect first"
  - Connect button was disabled (greyed out) because UI thought device was already connected
  - User had to disconnect then reconnect to fix the state

 **Root Cause:**
  - `ThorlabsWrapperDevice._attach_to_existing_supervisor()` set `DeviceState.READY` when wrapper subprocess was running
  - But wrapper running ≠ camera connected! The bridge's `self.connected` flag was still False
  - The control panel interpreted `DeviceState.READY` as "Connected" and disabled the Connect button

 **Solution:**
  - Modified `_attach_to_existing_supervisor()` to query wrapper's actual status
  - Checks `response['details']['connected']` to determine if camera is truly connected
  - Only sets `DeviceState.READY` if camera is actually connected
  - Otherwise keeps `DeviceState.OFFLINE` - wrapper ready, but user must click Connect

 **Behavior Now Matches Gamry/PI XYZ:**
  - Wrapper starts during GUI splash screen
  - Panel shows "Disconnected" / "Ready" (wrapper ready)
  - User clicks Connect to connect hardware
  - Panel shows "Connected" only after successful hardware connection

 **Files Modified:**
  - `src/devices/thorlabs_wrapper_device.py` - `_attach_to_existing_supervisor()` now queries actual camera status

 **Testing:**
  - 32/32 executor unit tests pass
  - Manual validation: Launch GUI, verify Thorlabs shows "Disconnected" until Connect clicked

17) Thorlabs Serial Number Display Fix (reliability branch - 2025-12-18)
 - **Status**: COMPLETE - Thorlabs now shows model and serial number like Gamry

 **Problem Solved:**
  - After connecting Thorlabs, status showed "Connected: Unknown" instead of camera model/serial
  - Gamry showed "Connected: PC61010" with proper model, but Thorlabs did not

 **Root Cause:**
  - Model/serial data was returned in `result.data["capabilities"]` nested dict
  - Control panel expected `result.data["model"]` and `result.data["serial"]` at top level
  - Gamry's wrapper returns model/serial at top level; Thorlabs wrapper didn't

 **Solution:**
  - Modified `ThorlabsWrapperDevice._do_connect()` to return model/serial at top level
  - Added fallback in `ThorlabsControlPanelV2._on_connect_result()` to read from device's `camera_capabilities` property
  - Added caching of camera model/serial for status display updates
  - Enhanced reconnect retry logic (3 attempts with 3s delays) for USB stability

 **Behavior Now:**
  - After connecting, shows "Connected: CS165CU (S/N: 33012)" in status label
  - Model/serial persists through state changes until disconnect
  - Matches Gamry's display pattern

 **Files Modified:**
  - `src/devices/thorlabs_wrapper_device.py` - Return model/serial at top level, improved reconnect retry
  - `src/thorlabs_control_panel_v2.py` - Fallback capabilities lookup, model/serial caching

 **Testing:**
  - Manual validation: Connect Thorlabs, verify "Connected: CS165CU (S/N: 33012)" displayed
  - All 3 devices (Gamry, PI XYZ, Thorlabs) connect and operate without crashes

18) Checkpoint/Resume (reliability branch - 2026-01-09)
 - **Status**: COMPLETE - Full GUI resume functionality

 **Checkpoint Creation:**
  - Sequences create `checkpoint.json` in session folder during execution
  - `sequence_definition.json` saves step definitions for resume support
  - Atomic write pattern prevents corruption (write to .tmp, rename)

 **GUI Resume:**
  - **File > Resume Session (Ctrl+R)**: Select checkpoint.json to resume
  - **Startup notification**: Orphan checkpoints logged to run panel (no popup)
  - **ResumeDialog**: Shows session info, progress, Gamry safety warning
  - **Sequence table**: Populated with completed/pending step states

 **Executor Resume:**
  - `GamrySequenceExecutor.start_from_checkpoint()` - Resume Gamry sequences
  - `MixedSequenceExecutor.start_from_checkpoint()` - Resume mixed sequences
  - Fallback reconstruction for older checkpoints without sequence_definition.json

 **Files:**
  - `src/utils/checkpoint_manager.py` - Checkpoint state management
  - `src/widgets/resume_dialog.py` - Resume session dialog
  - `src/controllers/resume_controller.py` - Resume workflow coordination
  - `src/executors/base_executor.py` - Sequence definition save/load

 **CLI (existing):**
  - `python src/run_cli.py find-checkpoints` - List orphaned checkpoints
  - `python src/run_cli.py resume <path>` - Resume from checkpoint

19) Resource Monitoring & Watchdog (reliability branch - 2026-01-08)
 - **Status**: Phase 3A/3B/3C COMPLETE - Full resource and command monitoring

 **Phase 3A - ResourceMonitor:**
  - `src/utils/resource_monitor.py` - Memory/disk monitoring with Qt signals
  - Configurable thresholds: warning (1GB), critical (2GB), disk (1GB free)
  - GUI toast warnings when thresholds exceeded
  - 30-second check interval via QTimer

 **Phase 3B - Command Watchdog:**
  - `DeviceSupervisor.check_command_watchdog()` - Detects stuck commands
  - Integrated into heartbeat loop for continuous monitoring
  - Fires `on_command_stuck` callback when timeout exceeded
  - GUI displays warning toast with command details

 **Phase 3C - Frame Backpressure:**
  - `CameraController._on_frame_ready()` - Pending frame tracking
  - MAX_PENDING_FRAMES=5 prevents unbounded queue growth
  - Bridge calls `frame_consumed()` to enable accurate tracking
  - Backpressure stats available via `get_backpressure_stats()`

 **Files Added/Modified:**
  - `src/utils/resource_monitor.py` (NEW)
  - `src/device_supervisor.py` - Watchdog methods
  - `src/command_dispatcher.py` - Tracking integration
  - `src/supervisor_service.py` - command_stuck signal
  - `src/camera/controller.py` - Backpressure
  - `scripts/thorlabs_bridge.py` - frame_consumed() call
  - `src/goed_gui_v3.py` - Handlers for all Phase 3 features

 **Testing:**
  - 55 unit tests: `python -m unittest tests.test_resource_monitor tests.test_command_watchdog tests.test_camera_backpressure`
  - Hardware validation: Live view stable at 13-16 FPS during Array Mode run

20) EIS Initial Delay Feature (reliability branch - 2026-01-14)
 - **Status**: COMPLETE - EIS Initial Delay (measure Eoc before sweep) fully functional

 **What's New:**
  - EIS panel checkbox "Initial Delay (Measure Eoc)" enables pre-sweep OCV measurement
  - Configurable delay time (1-400000s) and stability threshold (mV/s)
  - If stability < threshold before time expires, OCV phase ends early
  - Cell is turned OFF during OCV measurement, then ON for EIS frequency sweep

 **Files Modified:**
  - `src/widgets/eis_panel.py` - UI controls for Initial Delay (checkbox, time, stability)
  - `src/sequence/technique_schemas.py` - Conditional validation (skip when disabled)
  - `src/command_dispatcher.py` - Preserve Initial Delay params in EIS normalization
  - `src/describe_handler.py` - Allow GOED-defined params through validation
  - `src/utils/gamry_param_normalizer.py` - Timeout includes Initial Delay time
  - `src/goed_gui_v3.py` - Initial Delay in EIS summary logging

 **Gamry Repo Files Modified:**
  - `src/goed_entry.py` - _normalize_eis_params() includes Initial Delay params
  - `src/echem/core/curves/eis.py` - Cell ON before frequency sweep

 **Testing:**
  1. Launch GUI: `python src/goed_gui_v3.py`
  2. Select EIS technique in Gamry panel
  3. Check "Initial Delay (Measure Eoc)" box
  4. Set delay time (e.g., 10s) and stability (0.05 mV/s)
  5. Run EIS - potentiostat should wait for OCV before sweep

21) Long-Run Reliability (reliability branch - 2026-01-09)
 - **Status**: IN PROGRESS - Policy framework complete, integration pending

 **Implemented:**
  - Policy Layer: `PlotPolicy`, `ExportPolicy`, `LongRunPolicy` dataclasses
  - Factory presets: `for_long_chrono()`, `for_many_cycles_cv()`, `for_overnight_run()`
  - PowerManager for Windows sleep prevention (`ctypes.windll.kernel32.SetThreadExecutionState`)
  - LongRunController for coordinating long-run features
  - Cycle indicator display ("Cycle: X/Y") during CV/LSV runs
  - Debug logging for export policy flow tracing

 **Files Added:**
  - `src/policies/__init__.py` - Policy package
  - `src/policies/plot_policy.py` - PlotPolicy dataclass (rolling window, cycle limits, decimation)
  - `src/policies/export_policy.py` - ExportPolicy dataclass (PNG budget, logarithmic strategy)
  - `src/policies/long_run_policy.py` - Aggregate LongRunPolicy + factory presets
  - `src/utils/power_manager.py` - Windows power management (sleep/display prevention)
  - `src/controllers/long_run_controller.py` - Long-run feature coordination

 **Files Modified:**
  - `src/executors/gamry_sequence_executor.py` - Pass export_policy to export helpers
  - `src/executors/mixed_sequence_executor.py` - Accept plot_widget parameter
  - `src/executors/array_mode_executor.py` - Accept plot_widget parameter
  - `src/widgets/ec_plot_widget.py` - Cycle indicator, target cycles display
  - `src/goed_gui_v3.py` - Policy instantiation, pending_target_cycles tracking
  - `src/utils/export_helpers.py` - Export policy parameter, logging

 **⚠️ Known Issues (TODO):**
  - [ ] **PNG export policy not applied**: Logarithmic strategy set but all PNGs still generated
    - Export policy is passed to `generate_sequence_exports()` correctly
    - `should_export_png()` check may not be called in the right location
    - Need to trace full export flow and verify policy check execution
  - [ ] **Cycle eviction not reducing point count**: Points oscillate 18K-20K instead of ~3K for 10 cycles
    - Policy shows `max_displayed_cycles=10`, `evict_during_acquisition=True`
    - Eviction check may not trigger during acquisition phase
  - [ ] **Screen darkening after 5 minutes**: PowerManager may not be engaging correctly
    - Acceptable for now; needs verification of SetThreadExecutionState call

 **Testing Long-Run:**
  1. Launch GUI: `python src/goed_gui_v3.py`
  2. Run 30+ cycle CV to verify cycle indicator displays "Cycle: X/30"
  3. Check runs/ folder for PNG count (should be ~10 for logarithmic, not 30)
  4. Monitor point count during CV (should stabilize ~3K with 10-cycle limit)

22) CV/LSV Cycle Termination & Equilibration Time Fix (reliability branch - 2026-01-14)
 - **Status**: COMPLETE - CV/LSV now stop at assigned cycle count, equilibration time works for all techniques

 **Issue Fixed:**
  - CV/LSV would run indefinitely until timeout, ignoring assigned cycle count
  - Root cause: Architecture conflict between external loop in `goed_entry.py` and internal multi-cycle in orchestrator
  - CV's `signal_r_up_dn_new` has a `cycles` parameter (device handles multi-cycle internally)
  - LSV's `signal_ramp_new` does NOT have cycles parameter (requires external loop)

 **Solution:**
  - **CV**: Removed external loop. Single `run_step()` call with orchestrator handling multi-cycle splitting
  - **LSV**: Restored external loop with `cycles=1` override so orchestrator doesn't try to split by cycle field
  - **CA/CP**: Added `equilibration_time_s` to `_normalize_chrono_params()` (was missing)

 **Gamry Repo Files Modified:**
  - `src/goed_entry.py:300-351` - CV uses single `run_step()`, orchestrator splits by cycle field
  - `src/goed_entry.py:398-446` - LSV uses external loop (signal_ramp_new doesn't support multi-cycle)
  - `src/goed_entry.py:594` - Added `equilibration_time_s` to `_normalize_chrono_params()`

 **Testing:**
  1. CV with cycles=3 → Should stop after exactly 3 cycles, generate 3 CSV files
  2. LSV with cycles=3 → Should run 3 separate sweeps with smooth transitions
  3. CA with equilibration_time_s=5 → Should wait 5s at setpoint before acquisition
  4. CP with equilibration_time_s=5 → Should wait 5s at setpoint before acquisition

23) Sequence Integration of Single-Run Features (reliability branch - 2026-01-16)
 - **Status**: COMPLETE - IR compensation, equilibration time, and EIS initial delay now work in sequences

 **Issue Fixed:**
  - IR compensation, equilibration time, and EIS initial delay parameters were only applied in single runs
  - When adding steps to sequence or during sequence execution, these parameters were dropped
  - Root cause: `normalize_gamry_params()` built a new dict with only core params, dropping new features

 **Solution:**
  - **Parameter Normalization**: Updated `normalize_gamry_params()` to preserve new params:
    - CV/LSV: `equilibration_time_s`, `ir_comp_enable`, `ir_comp_ru_ohms`
    - CA: `equilibration_time_s`, `ir_comp_enable`, `ir_comp_ru_ohms`
    - CP/OCV: `equilibration_time_s`
    - EIS: `initial_delay_enabled`, `initial_delay_time_s`, `initial_delay_stability_mV_s`
  - **Table Display**: Updated sequence table to show new params (Eq. time, iR comp, Init delay)
  - **sequence-info.txt**: Added new params to human-readable output
  - **CV Overlay Naming**: Changed from `CV_overlay.png` to `Step{N:03d}_CV_overlay.png` to avoid overwrites

 **Files Modified:**
  - `src/utils/gamry_param_normalizer.py` - Preserve new params in normalization
  - `src/widgets/sequence_table_widget.py` - Display new params in table
  - `src/goed_gui_v2.py` - Display new params in legacy table
  - `src/gui_experimental/widgets/sequence_table_widget.py` - Display new params in experimental table
  - `src/utils/storage.py` - Add new params to sequence-info.txt output
  - `src/utils/export_helpers.py` - Include step index in overlay filenames

 **Testing:**
  1. Add CV step with equilibration_time=5s, ir_comp_enable=True, ir_comp_ru=10Ω
  2. Verify table shows "Eq. time: 5.0 s" and "iR comp: 10 Ω"
  3. Run sequence → verify wrapper receives params, technique applies them
  4. Check sequence-info.txt for "Eq Time=5.0 s, iR Comp=10.00 Ω" in step line
  5. Run sequence with 2+ CV steps → verify overlay files are `Step001_CV_overlay.png`, `Step002_CV_overlay.png`

24) Splash Screen Redesign (reliability branch - 2026-01-19)
 - **Status**: COMPLETE - Modern animated splash screen with themed device indicators

 **What's New:**
  - Consolidated all splash screen code into single file: `src/widgets/splash_screen.py`
  - `CircularTextLoader` - CSS-to-PySide6 converted orbital animation (GOED letters + cat/dog SVG icons)
  - `DeviceRingIndicator` - Lab console style circular progress rings for device status
  - Theme-aware colors using `Theme` class from `src/theme.py`
  - 2-line center text format: status action ("starting") + detail ("gamry...")

 **Animation Features:**
  - 10 orbiting elements: G-O-E-D-DOG-G-O-E-D-CAT in clockwise rotation
  - 60fps animation using QElapsedTimer + QTimer
  - SVG icons loaded once via QGraphicsSvgItem (not redrawn each frame)
  - Dynamic SVG coloring: replaces hardcoded fill with Theme.PRIMARY_100 at runtime
  - Orbital "breathing" effect at 50% of 1-second cycle

 **Device Status Indicators:**
  - Circular progress rings (28px diameter, 3px stroke)
  - States: waiting (gray), starting (animated pulse), ready (filled), failed (X mark)
  - Monospace "Consolas" font for device labels (GAMRY, STAGE, CAM)
  - Animations stop automatically when status changes from "starting"

 **Color Mapping (follows ACTIVE_PALETTE):**
  - Letters & Icons: Theme.PRIMARY_100
  - Center status line 1: Theme.ACCENT_100
  - Center status line 2: Theme.ACCENT_200
  - Device ring backgrounds: Theme.ACCENT_200
  - Ready state: Theme.PRIMARY_100
  - Starting state: Theme.PRIMARY_200
  - Failed state: Theme.PRIMARY_300
  - Background: Theme.BG_200, Glow: Theme.BG_300

 **Files:**
  - `src/widgets/splash_screen.py` - Main consolidated file (CircularTextLoader, DeviceRingIndicator, DeviceStatusBar, SplashScreen)
  - `src/widgets/assets/cat.svg` - Cat silhouette icon
  - `src/widgets/assets/dog.svg` - Dog silhouette icon
  - `src/widgets/__init__.py` - Exports SplashScreen, CircularTextLoader

 **Deleted Files:**
  - `src/gui_experimental/widgets/splash_screen.py` - Outdated duplicate
  - `src/widgets/rotating_rings_loader.py` - Unused (superseded by CircularTextLoader)
  - `src/widgets/circular_text_loader.py` - Merged into splash_screen.py

 **Testing:**
  - Standalone demo: `python src/widgets/splash_screen.py`
  - Shows animated loader with device status transitions (starting → ready/failed)

25) Live Sequence Editing (reliability branch - 2026-02-03)
 - **Status**: ✅ IMPLEMENTATION COMPLETE — Hardware validated
 - **See**: `docs/features/LIVE_SEQUENCE_EDITING_PLAN.md` for full implementation details

 **Capabilities Delivered:**
  - ✅ Edit technique parameters for pending steps during execution
  - ✅ Edit PStat/context parameters for pending steps during execution
  - ✅ Add new steps after current executing step (via shadow sequence API)
  - ✅ Delete pending steps during execution (via shadow sequence API)
  - ✅ Reorder pending steps during execution (via shadow sequence API)
  - ✅ Table display refreshes when edits are applied
  - ✅ Checkpoint integration for crash recovery

 **Architecture Implemented:**
  - **Shadow Sequence Pattern** + UUID-based step identity
  - Edits staged in parallel "shadow" copy, atomically applied at safe sync points
  - Thread-safe by design (single-threaded execution, no locks needed)
  - Deep copy on initialization prevents shared reference bugs

 **Files Created:**
  - `src/models/step_data.py` — StepData, StepId, ExecutionState types (180 LOC)
  - `src/models/shadow_sequence.py` — ShadowSequenceManager (500 LOC)
  - `src/models/edit_result.py` — EditResult enum (29 LOC)
  - `tests/test_shadow_sequence.py` — 47 unit tests

 **Files Modified:**
  - `src/executors/base_executor.py` — Live editing API methods, checkpoint integration
  - `src/executors/gamry_sequence_executor.py` — Shadow sequence read/write at sync points
  - `src/executors/mixed_sequence_executor.py` — Shadow sequence support
  - `src/widgets/sequence_table_widget.py` — Live editing UI, pending indicator, table refresh
  - `src/utils/checkpoint_manager.py` — Pending edits persistence

 **Bug Fixes Applied (2026-02-03):**
  1. **Shared params reference bug**: Deep copy in `StepData.from_dict()` prevents editing one step from affecting others
  2. **Table not refreshing**: Connected `edit_applied` signal to `_on_edits_applied()` handler

 **Gap Fixes Applied (2026-02-03):**
  1. **Gap 1 — Add/Delete/Reorder disabled during execution**:
     - Kept structural buttons enabled in `set_running()` (they validate step state before operating)
     - Updated `_on_delete_step()`, `_on_move_up()`, `_on_move_down()` to route to shadow sequence when running
     - Updated `_add_gamry_step()`, `_add_pi_step()` to route to `shadow.request_insert()` when running
     - Connected `sequence_modified` signal for immediate table refresh on queued changes
     - Updated `_on_edits_applied()` and `_refresh_from_shadow_sequence()` to fully rebuild steps list
  2. **Gap 2 — Sidecar files recording original values instead of edited**:
     - Modified both executors' `_finish_sequence()` to use `shadow.get_active_steps_as_dicts()`
     - Manifest, sequence_definition.json, and sequence-info.txt now record edited values

 **Executor Integration Bug Fixes (2026-02-06):**
  1. **Tracking arrays not resized after structural edits**: Added `_sync_tracking_arrays()` to both executors — resizes `_step_artifacts`/`_step_status` and syncs `self._steps` from shadow after `apply_pending_edits()`
  2. **`handle_step_result` reads stale `self._steps`**: Technique now read from shadow sequence current step instead of `self._steps[self._index]`
  3. **Bounds checks on tracking arrays**: Added bounds guards on `_step_status[self._index]` and `_step_artifacts[self._index]` to prevent IndexError
  4. **`start_from_checkpoint` missing shadow sequence**: Both executors now initialize `ShadowSequenceManager` during checkpoint resume, mark completed steps, wire signals, restore from `pending_edits` if present
  - **Tests**: 11 new integration tests in `tests/test_executor_live_editing.py` (58 total with shadow sequence tests)

 **New Types Created:**
  ```python
  class StepId:           # Immutable UUID-based identifier
  class ExecutionState:   # PENDING, RUNNING, COMPLETED, FAILED, SKIPPED
  class StepData:         # id, technique, params, device, state, context_overrides
  class EditResult:       # SUCCESS, STEP_NOT_FOUND, STEP_NOT_EDITABLE, VALIDATION_FAILED, QUEUED
  class ShadowSequenceManager:  # Manages active/pending lists with atomic swap
  ```

 **Critical Code Locations:**
  - `src/executors/gamry_sequence_executor.py:117` — Current shallow copy (`steps.copy()`)
  - `src/executors/gamry_sequence_executor.py:215` — `_execute_next_step()` reads from `self._steps`
  - `src/widgets/sequence_table_widget.py:969-985` — `set_running()` disables edit controls
  - `src/utils/checkpoint_manager.py` — Atomic write pattern to reuse

 **Existing Patterns to Leverage:**
  - Lock hierarchy from `device_supervisor.py:77-86`
  - Atomic write from `checkpoint_manager.py`
  - Signal-based state updates throughout GUI
  - Circuit breaker pattern from `src/utils/circuit_breaker.py`

 **Testing Requirements:**
  - ~57 unit tests for ShadowSequenceManager
  - ~23 integration tests for UI-executor flow
  - Manual hardware tests for edit-during-execution scenarios
  - All existing tests must remain green

 **Implementation Validation Commands:**
  ```bash
  # Run new unit tests (after Phase 1)
  python -m pytest tests/test_shadow_sequence.py -v

  # Run all executor tests (after Phase 2)
  python -m pytest tests/test_executors.py -v

  # Launch GUI for manual testing (Phase 3+)
  python src/goed_gui_v3.py

  # Full test suite
  python -m pytest tests/ -v
  ```

 **Risk Mitigations:**
  - Thread safety via atomic swap pattern (no shared mutation during execution)
  - UUID-based identity handles insert/delete/reorder gracefully
  - Checkpoint includes pending edits for crash recovery
  - Re-validation on apply prevents invalid states

 **Success Criteria:**
  1. ✅ User can edit technique parameters of pending steps during execution
  2. ✅ User can edit PStat parameters of pending steps during execution
  3. ✅ User can add new steps after current executing step
  4. ✅ User can delete pending steps
  5. ✅ User can reorder pending steps
  6. ✅ Edits apply atomically at safe sync points
  7. ✅ No race conditions or data corruption
  8. ✅ All existing tests continue to pass
  9. ✅ Checkpoint/resume preserves pending edits

26) GUI Splitter & Panel Layout Polish (reliability branch - 2026-02-03)
 - **Status**: COMPLETE - v3 layout restores expected initial split and safe minimum width

 **What Changed:**
  - Enforced initial 30/70 left/center splitter ratio on first show (uses actual window width).
  - Added computed minimum width for left panel so controls remain visible at compact size.

 **Files Modified:**
  - `src/goed_gui_v3.py` - initial ratio logic and left panel min width calculation

 **Testing:**
  1. Launch GUI: `python src/goed_gui_v3.py`
  2. Verify initial 30/70 ratio
  3. Drag left splitter to minimum width - all controls remain visible

27) Analysis Module Enhancements (reliability branch - 2026-02-04)
 - **Status**: COMPLETE - Overlay plot legends and calculation questionnaire

 **Overlay Plot Legends:**
  - Added `addLegend(offset=(10, 10))` to all 8 plot widgets across both canvas files
  - Legends display trace names (already passed via `name=label` in plot calls)
  - Fixed legend persistence after `PlotWidget.clear()` in `_redraw_all()`

 **Files Modified:**
  - `src/analysis/plot_canvas.py` - Added legends to main_plot, nyquist_plot, bode_mag_plot, bode_phase_plot; re-add in `_redraw_all()`
  - `src/analysis/multi_plot_canvas.py` - Added legends to plot_widget, nyquist_plot, bode_mag_plot, bode_phase_plot in TechniquePlotWidget

 **Calculation Questionnaire:**
  - Created `docs/features/ANALYSIS_CALCULATIONS_QUESTIONNAIRE.md` for lab mates to specify desired calculations
  - Documents exact CSV column headers for each technique (OCV, CA, CP, LSV, CV, EIS)
  - Based on actual GOED CSV exports from `runs/` folder
  - Follows principles: data source restriction, formula traceability, technique specificity

 **Validation:**
  - 12 test scenarios passed: view switching, trace toggling, EIS views, clear/redraw
  - Legends visible and correctly labeled for all technique types

28) Analysis Session Refresh + Manifest Artifact Resolution (reliability branch - 2026-02-06)
 - **Status**: COMPLETE - Analysis list updates after each completed step and robust artifact linking for exports/plots

 **What Changed:**
  - Analysis session browser auto-refreshes on manifest changes (polls every 2s, preserves expanded sessions)
  - Sequence executors write manifest snapshots after each completed step
  - Manifest writer resolves missing artifacts by searching the session folder with `Step{N}_{TECH}*.csv`

 **Files Modified:**
  - `src/analysis/session_browser.py` - auto-refresh + manifest change detection
  - `src/executors/gamry_sequence_executor.py` - manifest snapshot on step completion
  - `src/executors/mixed_sequence_executor.py` - manifest snapshot on step completion
  - `src/utils/export_helpers.py` - artifact path resolution for manifests

 **Validation:**
  - Hardware run: Analysis session list updated after step completion; EIS step plotted once manifest resolved

29) Installation Guidance Hardening (2we branch - 2026-02-11)
 - **Status**: COMPLETE - New-PC install docs now include lab package source and privilege model

 **What Changed:**
  - Added explicit official vendor suite source path: `D:\SEM\GOED\installation`
  - Documented admin vs user split:
    - Administrator: vendor suite/driver installs (Gamry/PI/Thorlabs)
    - User: Python install, venv creation, pip installs, normal GOED runs
  - Updated setup docs to require PI/Thorlabs packages from installation store and Gamry guidance from same store
  - Clarified missing-config failure message in loader with actionable fix
  - Added `GOED_CONFIG_PATH` support for active entrypoints:
    - GUI v3 (`src/goed_gui_v3.py`)
    - bootstrap config resolution (`src/app/bootstrap.py`)
    - CLI defaults (`src/run_cli.py`, `src/supervisor_cli.py`)

 **Files Modified:**
  - `README.md`
  - `docs/setup/NEW_PC_SETUP.md`
  - `docs/setup/SETUP_GUIDE.md`
  - `src/config_loader.py`
  - `src/app/bootstrap.py`
  - `src/goed_gui_v3.py`
  - `src/run_cli.py`
  - `src/supervisor_cli.py`

 **Validation:**
  - Syntax check: `python -m py_compile src/config_loader.py src/app/bootstrap.py src/goed_gui_v3.py src/run_cli.py src/supervisor_cli.py`
  - Unit test: `python -m pytest tests/test_describe_flow.py -q`
  - Known flaky/manual gap: `tests/test_command_dispatcher.py` aborts in this environment with `QThread: Destroyed while thread '' is still running`

30) 2WE Cycle-42 Truncation Investigation + Sampling Model UI Guardrail (2we branch - 2026-02-25)
 - **Status**: COMPLETE (code patch + tests) / HARDWARE RERUN PENDING

 **What Changed:**
  - Saved investigation report for repeatable 2WE stop-at-cycle-42 issue:
    - `docs/2we/2WE_CYCLE42_REPEATABLE_TRUNCATION_INVESTIGATION_2026-02-25.md`
  - CV/LSV panel sample rate is now derived/read-only from `scan_rate / step_size_V`
    - Prevents user-editable CV sample-rate mismatch in GOED UI
  - Added GOED regression tests for CV panel sampling-rate behavior
  - External Gamry wrapper patch set (separate repo) completed:
    - Dynamic CV/Chrono curve buffer sizing (removes fixed 100000-point cap issue for long runs)
    - CV effective sampling policy normalization + preflight mismatch warnings
    - Timing audit underrun detection (not just overshoot)
    - `segment_incomplete` / `DUAL_SEGMENT_INCOMPLETE` propagation on timing underrun
    - Mixed-cycle postprocess appends corrected dual completion event with corrected row count

 **Files Modified (GOED):**
  - `src/widgets/cv_panel.py`
  - `tests/test_cv_panel_sampling_rate.py`
  - `docs/2we/2WE_CYCLE42_REPEATABLE_TRUNCATION_INVESTIGATION_2026-02-25.md`

 **Validation:**
  - GOED unit tests: `pytest tests/test_cv_panel_sampling_rate.py -q` (pass)
  - Gamry targeted regressions (separate repo): curve-cap/sampling + timing underrun + 2WE mixed postprocess tests (pass)
  - Hardware rerun still required: repeat 50-cycle CV + 1200 s CA 2WE sequence and confirm no truncation + correct completion reporting
