# PI_XYZ – PI Stage Control System

This repository contains both the new object-oriented PI stage control system and the legacy production GUI. The new codebase follows a layered architecture defined in `docs/architecture/`, separating domain models, hardware adapters, services, and PySide6 GUI. Every session should start by following the checklist in `docs/README_DAILY.md`.

## Repository Layout

```
PI_Control_System/   # New OOP codebase (models, hardware, services, GUI stubs, tests)
docs/                # Architecture guidance, implementation plan, daily checklist
legacy/              # Original GUI, scripts, vendor DLLs, and reference docs
artifacts/           # Session artifacts (test results, run logs)
```

### PI_Control_System
- `core/` – Dataclasses, enums, and exception hierarchy.
- `hardware/` – Future hardware interfaces and PI-specific implementations.
- `services/` – Event bus and orchestration services (under construction).
- `gui/` – Modular widgets and controllers to be implemented in upcoming phases.
- `config/` – Configuration loader and packaged defaults.
- `tests/` – Pytest suite covering core models, configuration, and immutability guarantees.

Run the test suite:

```bash
python -m pytest PI_Control_System/tests
```

### Legacy Assets
Everything that powered the original production GUI (PySide6 app, helper scripts, DLLs, documentation) now lives under `legacy/`. Nothing inside this directory is imported by the new architecture—it is preserved strictly for reference and fallback.

## Configuration

Default hardware settings are stored in `PI_Control_System/config/defaults.json`. To override locally without touching version control, create a `local.overrides.json` at the repository root or set the `PI_STAGE_CONFIG_PATH` environment variable to point at a custom JSON file. You can also use the provisioning CLI to inspect and update overrides:

```bash
python -m PI_Control_System.config.cli show
python -m PI_Control_System.config.cli set-port X COM7
python -m PI_Control_System.config.cli set-park-position 185.0
```

The loader deep-merges package defaults, package/root overrides, environment overrides, and any explicit path before falling back to hardcoded values.

## Running the Application

The system supports dual-launch mode for gradual migration:

```bash
# Launch new OOP GUI (recommended)
python pi_control_system_app.py

# Launch with mock hardware (for testing without physical stages)
python pi_control_system_app.py --mock

# Launch legacy GUI (fallback)
python pi_control_system_app.py --legacy
```

The new GUI provides the same functionality as the legacy version with improved architecture:
- Clean separation of concerns (models, hardware, services, GUI)
- Thread-safe event-driven updates
- Comprehensive test coverage (123 passing tests, 91% coverage)
- Centralized configuration management
- Real-time position display (100ms polling)
- Manual jog and automated sequence modes
- Safe park sequence (Z-first, then X/Y simultaneous)

## Development Status

Implementation proceeds according to `docs/architecture/IMPLEMENTATION_PLAN.md`.

**Completed Phases:**
- ✓ Phase 0: Preparation (project skeleton, legacy assets preserved)
- ✓ Phase 1: Core Models (dataclasses, enums, errors)
- ✓ Phase 2: Hardware Layer (interfaces, PI controllers, mock implementations)
- ✓ Phase 3: Service Layer (EventBus, ConnectionService, MotionService)
- ✓ Phase 4: Configuration System (loader, schema, CLI)
- ✓ Phase 5: GUI Layer (widgets, controllers, MainWindow)
- ✓ Phase 6: Integration (dependency injection factory, launcher)
- ✓ Phase 7: Testing and Validation (91% coverage, 123 tests, hardware validation complete)

**Hardware Validation Complete (Nov 7, 2024):**
- All features tested with real PI USB stages
- Position polling working (100ms updates)
- Velocity controls apply to hardware
- Sequence execution validated
- Park-on-close and disconnect working
- All legacy origintools.py functions integrated
- See `docs/HARDWARE_VALIDATION_LOG.md` for details

**Next Milestone:**
- **Phase 8: Rollout** - Operator training, production use, feedback collection
