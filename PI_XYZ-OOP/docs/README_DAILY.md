# Daily Session Kickoff Checklist

Use this checklist at the start of every working session to ensure the project stays aligned with the architecture plan.

1. **Read the Architecture Overview**
   - `docs/architecture/ARCHITECTURE.md` (high-level guidance)
   - `docs/architecture/INTERFACES.md` (contracts for the layer you are touching)

2. **Consult the Implementation Plan**
   - `docs/architecture/IMPLEMENTATION_PLAN.md`
   - Start at the next incomplete phase/task (Phase 8 – Rollout is next in queue).

3. **Review Latest Status**
   - `README.md` (repository layout and current focus)
   - `docs/architecture/APPENDICES.md` (risks, spike logs, sign-off checklist)
   - `docs/HARDWARE_VALIDATION_LOG.md` (hardware test results and known issues)

4. **Environment Checks**
   - Activate the project venv (`.venv`) if available.
   - `pip install -r requirements.txt` (PySide6 / pipython) as needed.

5. **Verify Baseline Health**
   - Run automated tests: `python -m pytest PI_Control_System/tests -v`
   - All 123 tests should pass (91% coverage as of Phase 7)
   - Coverage reports are stored in `artifacts/test_reports/`

6. **Current Project Status (Phase 7 Complete)**
   - **Core Architecture**: All layers implemented (models, hardware, services, GUI, config)
   - **Hardware Integration**: Validated with real PI stages (all issues resolved)
   - **GUI Features**: Position polling, velocity control, manual jog, automated sequences, park-on-close
   - **Test Suite**: 123 passing tests covering all components
   - **Known Working Features**:
     * Connection/initialization with USB PI stages
     * Real-time position display (100ms polling)
     * Manual jog controls with safety clamping
     * Automated waypoint sequences
     * Safe park sequence (Z first, then X/Y simultaneous)
     * Mode switching (manual/automatic)

7. **Next Session Tasks**
   - Phase 8 – Rollout: Operator training and feedback collection
   - Performance optimization if needed
   - Additional sequence features based on user requests

By following this checklist you ensure every session begins with an up-to-date understanding of the architecture, current status, and testing requirements.
