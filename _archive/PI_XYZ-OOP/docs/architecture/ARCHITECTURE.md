# OOP Refactor - Architecture Specification

## 1. Purpose
Deliver a concise, actionable blueprint for rebuilding the PI stage control system with a clean object-oriented architecture. This replaces the previous seven-part narrative with a practical description of responsibilities, dependencies, and success criteria.

## 2. Context Snapshot (Master Branch)
- `PI_Control_GUI/main_gui.py` (lines 59-787): monolithic Qt window handling layout, hardware orchestration, threading, logging.
- `PI_Control_GUI/hardware_controller.py` (lines 24-351): direct `pipython` access, velocity caching, reference routine, parking sequence.
- `origintools.py` (lines 9-101): safety helpers (`safe_range`, `reset`).
- `Tmotion2.0.py` (lines 20-190): canonical multi-axis motion workflow.

These references supply the algorithms cited throughout this document.

## 3. Target Layering
```
+-------------+
|  GUI Layer  |  (PySide6 widgets + controllers)
+------+------+ 
       consumes
+------+------+
|  Services   |  (event bus, connection/motion services)
+------+------+
       depends on
+-------------+
|    Core     |  (models, hardware interfaces, configuration)
+-------------+
```
Dependencies flow downward only: GUI never imports hardware; hardware never touches Qt.

## 4. Architectural Principles
1. **Explicit Interfaces** - All cross-layer dependencies use contracts documented in `INTERFACES.md`.
2. **Thread Safety** - Services own executors and hardware calls. GUI receives updates via Qt signals marshalled from service callbacks.
3. **Deterministic Configuration** - A typed loader merges defaults and local overrides, guaranteeing predictable settings.
4. **Test Isolation** - Models and hardware adapters run without Qt. Services run against mocks. GUI widgets can be exercised with stubbed services.
5. **Incremental Migration** - Legacy GUI remains runnable until feature parity is verified. The new app lives under `PI_Control_System/`.

## 5. Component Overview

### 5.1 Core Package (`PI_Control_System/core`)
- **Models**: immutable dataclasses (`Axis`, `AxisConfig`, `TravelRange`, `Position`, `Waypoint`, `SequenceConfig`, `SystemState`), derived from existing config and waypoint formats.
- **Hardware Interfaces**: abstract base classes for single-axis controller and controller manager (see `INTERFACES.md`).
- **Configuration**: loader that merges `defaults.json`, optional `local.overrides.json`, and a `PI_STAGE_CONFIG_PATH` override.
- **Errors**: typed exceptions (`ConnectionError`, `InitializationError`, `MotionError`) matching failure modes in `hardware_controller.py`.

### 5.2 Hardware Package (`PI_Control_System/hardware`)
- **PIAxisController**: wraps `pipython.GCSDevice`, encapsulating connect/reference/move/wait logic from `hardware_controller.py`.
- **PIControllerManager**: manages three `PIAxisController` instances, enforces the safe reference order `['Z', 'X', 'Y']`, and executes the parking sequence from `origintools.reset`.
- **MockAxisController**: deterministic simulator for unit tests (pattern borrowed from `pi_translator.py`).

### 5.3 Service Package (`PI_Control_System/services`)
- **EventBus**: thread-safe pub/sub with synchronous publish semantics and Qt-friendly guidance.
- **ConnectionService**: coordinates connect, initialise, disconnect operations; surfaces state transitions expected by the GUI.
- **MotionService**: performs absolute/relative moves, waypoint sequences, and parking using a shared executor; publishes progress events.
- **PositionService**: polls hardware at configurable intervals (default 100 ms) and debounces updates.

### 5.4 GUI Package (`PI_Control_System/gui`)
- **Widgets**: modular PySide6 widgets for connection controls, position display, velocity sliders, manual jog, waypoint table, and log view.
- **Controllers**: bridge services to widgets, ensuring all updates are marshalled via `QMetaObject.invokeMethod` to the main thread.
- **Main Window**: composes widgets, triggers service actions, and exposes launch hooks for both legacy and new flows.

## 6. Safety and Reliability Considerations
1. **Reference Order Enforcement** - Only the hardware layer knows the safe `['Z', 'X', 'Y']` order; services must work through the controller manager.
2. **Range Clamping** - `TravelRange.clamp()` centralises `safe_range` logic so every motion request is validated.
3. **Velocity Management** - `AxisState` caches velocity and clamps requests to `AxisConfig.max_velocity`.
4. **Failure Propagation** - Hardware exceptions are wrapped in typed errors and broadcast with axis context via `EventType.ERROR_OCCURRED`.
5. **Shutdown Guarantees** - `ConnectionService.disconnect()` is invoked in `finally` blocks to tidy up even when initialisation fails.

## 7. Migration Strategy
1. **Parallel Entry Points** - Legacy assets live under `legacy/` (former `run_gui.py`, `PI_Control_GUI/`, support scripts). Add a dedicated launcher (e.g., `pi_control_system_app.py`) for the new GUI.
2. **Feature Parity Checklist** - Use acceptance criteria in `IMPLEMENTATION_PLAN.md` to prove equivalence.
3. **Data Compatibility** - Keep config defaults aligned with `PI_Control_GUI/config.py`; rely on local overrides for site-specific tweaks.
4. **Rollback Plan** - Provide a command-line flag or environment variable (`PI_USE_NEW_GUI`) that selects between GUIs during rollout.

## 8. Success Criteria
- GUI package contains zero `pipython` imports.
- Hardware tests run headless using `MockAxisController`.
- Services respect the state machines defined in `INTERFACES.md`.
- Manual QA script verifies connect -> initialise -> jog -> sequence -> park -> disconnect with logged events.
- Implementation passes `ruff`, `mypy`, and `pytest` with at least 90% coverage on core/services.

## 9. Next Steps
Proceed to `INTERFACES.md` for concrete contracts, then `IMPLEMENTATION_PLAN.md` for the execution roadmap. Capture validation evidence and risks in `APPENDICES.md`.
