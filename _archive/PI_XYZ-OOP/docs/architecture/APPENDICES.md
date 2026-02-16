# OOP Refactor - Appendices

## A. Source Trace Map (Master Branch)

| Topic | Legacy Reference |
| --- | --- |
| Connection workflow | `PI_Control_GUI/hardware_controller.py:35-120` |
| Velocity management | `PI_Control_GUI/hardware_controller.py:121-204` |
| Position polling | `PI_Control_GUI/hardware_controller.py:215-247`, `main_gui.py:704-722` |
| Waypoint execution | `PI_Control_GUI/main_gui.py:666-687` |
| Parking sequence | `origintools.py:42-96` |
| Safe range clamping | `origintools.py:16-33` |
| GUI layout structure | `PI_Control_GUI/main_gui.py:159-513` |
| Threading pitfalls | `PI_Control_GUI/main_gui.py:530-573` |

Use this table when mapping tests or debugging mismatches between old and new systems.

## B. Spike Logs

### B1. Qt Threading / Event Dispatch
- **Goal**: Confirm that service events emitted from a `ThreadPoolExecutor` can safely update Qt widgets.
- **Procedure**:
  1. Create a minimal Qt window with a label; subscribe to `EventBus`.
  2. From a worker thread, publish an event; inside the callback use `QMetaObject.invokeMethod` with `Qt.QueuedConnection`.
  3. Observe the main-thread update and note any warnings.
- **Status**: Pending. Record latency, errors, and conclusions here after running.

### B2. Executor Sizing
- **Goal**: Ensure `max_workers=4` handles simultaneous connect/init/sequence tasks.
- **Procedure**:
  1. Run `MotionService.execute_sequence` against `MockAxisController` with more than ten waypoints.
  2. Measure completion time and queue depth.
  3. If saturation occurs, capture metrics and adjust worker count or task batching.
- **Status**: Pending.

### B3. Configuration Override Merge
- **Goal**: Validate merge order described in `IMPLEMENTATION_PLAN.md` section 4.
- **Procedure**:
  1. Create a temporary directory with `defaults.json` and `local.overrides.json`.
  2. Set `PI_STAGE_CONFIG_PATH` to reference an additional override file.
  3. Run the loader and verify precedence: defaults < local < env path.
- **Findings (Nov 7, 2025)**: Deep-merge loader honors package defaults, package/root overrides, env overrides, and explicit paths. Legacy root `defaults.json` and hardcoded bundle both participate when package defaults are absent. CLI tests confirm override persistence.
- **Status**: Complete.

Update each section with findings once spikes are executed.

## C. Glossary
- **Axis Controller** - Object responsible for one physical axis (connect, initialise, move, read position).
- **Controller Manager** - Aggregates axis controllers and enforces safe multi-axis sequences.
- **Event Bus** - In-process pub/sub mediator between services and GUI.
- **Sequence Config** - Collection of waypoints plus execution directives.
- **Travel Range** - Physical limits for stage travel, used to clamp motion requests.

## D. Risk Register

| ID | Risk | Impact | Mitigation |
| --- | --- | --- | --- |
| R1 | Event bus callbacks block GUI | High | Use short callbacks and Qt queued invocations; verify via spike B1 |
| R2 | Hardware exceptions leave axes enabled | High | Ensure `ConnectionService.disconnect()` runs in finally blocks; unit test failure paths |
| R3 | Configuration divergence across machines | Medium | Use config CLI + deep-merge loader to manage site overrides; document workflow |
| R4 | Migration fatigue (two GUIs) | Medium | Maintain `--legacy` flag until parity sign-off |
| R5 | Executor starvation | Medium | Execute spike B2; adjust worker count or split workloads |

## E. Stakeholder Sign-off Checklist
- [ ] Architecture reviewed by software lead.
- [ ] Hardware team validates controller abstraction.
- [ ] Operations sign off on migration/rollback plan.
- [ ] QA approves test coverage thresholds.

Keep this appendix updated as decisions and verifications occur.
