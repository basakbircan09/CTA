# OOP Refactor - Implementation Plan

This plan converts the architecture into executable work. Each task lists prerequisites, deliverables, verification steps, and effort estimates derived from the legacy system.

> **Status Update (Nov 7, 2025)**
> Phases 0-7 are complete (core foundation, hardware layer, service layer, configuration system, GUI layer, integration, testing/validation). Continue with Phase 8 (Rollout) next.

## Phase 0 - Preparation (0.5 h)
1. **Create package skeleton**
   - `PI_Control_System/` with subpackages: `core`, `hardware`, `services`, `gui`, `config`, `tests`.
   - Add `pyproject.toml` scaffolding (Poetry, uv, or pip-tools as preferred).
2. **Copy legacy assets for reference**
   - Preserve easy access to `PI_Control_GUI` code paths for side-by-side checks.

## Phase 1 - Core Foundation (1.5 h)
| Task | Description | Prerequisites | Acceptance Criteria |
| --- | --- | --- | --- |
| 1.1 | Implement dataclasses/enums per `INTERFACES.md` section 1 | Package skeleton | Unit tests cover `TravelRange.clamp`, `Position` indexing |
| 1.2 | Define typed exceptions | Task 1.1 | Exceptions raised with informative messages |
| 1.3 | Implement configuration loader stub | Task 1.1 | Loads defaults JSON, validates schema, fails gracefully when file missing |

## Phase 2 - Hardware Layer (3 h)
| Task | Description | Prerequisites | Acceptance Criteria |
| --- | --- | --- | --- |
| 2.1 | Write hardware interfaces module | Phase 1 | Signatures match `INTERFACES.md` section 3 |
| 2.2 | Implement `PIAxisController` | Task 2.1 | Unit tests (with `unittest.mock`) verify call order vs `hardware_controller.py` |
| 2.3 | Implement `PIControllerManager` | Task 2.2 | Enforces Z->X->Y initialisation and parking sequences; raises if axis missing |
| 2.4 | Build `MockAxisController` for tests | Task 2.1 | Deterministic behaviour reused by service tests |

**Spike 2.A - Qt threading compatibility (0.5 h)**  
Prototype publishing from a worker thread; marshal updates via `QMetaObject.invokeMethod`. Record findings in `APPENDICES.md` section B1. Success = no Qt warnings and main-thread UI updates.

## Phase 3 - Service Layer (3.5 h)
| Task | Description | Prerequisites | Acceptance Criteria |
| --- | --- | --- | --- |
| 3.1 | Implement `EventBus` with subscription tokens | Spike 2.A | Tests cover subscribe/unsubscribe/publish order and exception handling |
| 3.2 | Implement `ConnectionService` | Tasks 2.3, 3.1 | State transitions follow diagram; futures resolve; errors propagate |
| 3.3 | Implement `MotionService` | Tasks 2.3, 3.1 | Supports single-axis moves, sequences, cancel, park using executor |
| 3.4 | Implement `PositionService` | Tasks 2.3, 3.1 | Poller throttles updates; tested with mock controller |

**Spike 3.A - Executor sizing (0.25 h)**  
Exercise long waypoint sequence against mock hardware. Confirm `max_workers=4` avoids starvation. Document measurements in `APPENDICES.md` section B2.

## Phase 4 - Configuration System (1 h) ✅
| Task | Description | Prerequisites | Acceptance Criteria | Status |
| --- | --- | --- | --- | --- |
| 4.1 | Create `defaults.json` and schema | Phase 1 | Mirrors `PI_Control_GUI/config.py` values | Complete |
| 4.2 | Implement loader merge order | Task 4.1 | Tests verify precedence: defaults -> local -> env override | Complete (deep-merge loader + legacy fallback) |
| 4.3 | (Optional) CLI to generate local overrides | Task 4.2 | CLI writes `local.overrides.json`, handles duplicates | Complete (config CLI w/ tests) |

## Phase 5 - GUI Layer (4.5 h)
| Task | Description | Prerequisites | Acceptance Criteria | Status |
| --- | --- | --- | --- | --- |
| 5.1 | Build reusable widgets | Phases 1-4 | Widgets render with stubbed data; no direct service calls | Complete |
| 5.2 | Implement controllers bridging services | Task 5.1 | Qt tests confirm signal mapping; leverages spike 2.A pattern | Complete (deque log buffering) |
| 5.3 | Assemble `MainWindow` | Task 5.2 | Manual script verifies connect/init/jog/sequence/park/disconnect; log panel shows events | Complete |

## Phase 6 - Integration and Entry Point (1.5 h)
| Task | Description | Prerequisites | Acceptance Criteria | Status |
| --- | --- | --- | --- | --- |
| 6.1 | Wire dependency injection factory | Prior phases | All services share executor and config bundle | Complete (lazy PIAxisController import) |
| 6.2 | Create new launcher (`pi_control_system_app.py`) | Task 6.1 | CLI flag `--legacy` toggles old GUI | Complete |
| 6.3 | Update root README | Task 6.2 | Documents dual-launch strategy and new structure | Complete |

## Phase 7 - Testing and Validation (2 h)
| Task | Description | Acceptance Criteria | Status |
| --- | --- | --- | --- |
| 7.1 | Unit tests for core, hardware mocks, services | At least 90% coverage for core/services | Complete (91% coverage, 120 tests) |
| 7.2 | Integration script with real hardware | Checklist: connect -> initialise -> jog -> sequence -> park -> disconnect | Complete (tests/integration_test.py) |
| 7.3 | UI regression capture | Screenshots/logs demonstrating parity with legacy app | Complete (manual test + coverage doc) |

## Phase 7.5 - Hardware Validation (Pre-Rollout)
**REQUIRED before Phase 8:**
- [ ] Complete hardware validation checklist (`docs/HARDWARE_VALIDATION.md`)
- [ ] Verify safety features with real PI stages:
  - Initialization follows reference order (Z → X → Y)
  - Travel range limits enforced for all axes
  - Park sequence executes Z-first
  - Pre-init motion blocked
  - Velocity limits respected
- [ ] Sign-off in `docs/HARDWARE_VALIDATION.md`
- [ ] All critical safety tests pass (see `docs/VALIDATION_QUICKSTART.md`)

**Do NOT proceed to Phase 8 if any safety test fails.**

## Phase 8 - Rollout (0.5 h)
**Prerequisites:** Phase 7.5 hardware validation complete with sign-off

- Schedule operator dry run using both GUIs.
- Collect feedback, log issues in tracker.
- Tag release candidate once acceptance criteria met.

## Timeline (Conservative)
| Phase | Effort |
| --- | --- |
| 0 | 0.5 h |
| 1 | 1.5 h |
| 2 | 3 h |
| 3 | 3.5 h |
| 4 | 1 h |
| 5 | 4.5 h |
| 6 | 1.5 h |
| 7 | 2 h |
| 8 | 0.5 h |
| **Total** | **18 h** |

Estimates include coding and unit testing. Revisit after completing spikes.

## Verification Checklist
- [ ] Interface compliance audited against `INTERFACES.md`.
- [ ] Spike findings captured in `APPENDICES.md`.
- [ ] Feature parity demo recorded.
- [ ] Legacy/new UI toggle verified.

## Tooling Recommendations
- Adopt `ruff`, `mypy`, and `pytest` as baseline.
- Consider commit conventions (for example, conventional commits) for clarity during migration.

## Change Management
- Continue working on `OOP` branch; merge to `master` only after acceptance criteria pass.
- Retain legacy GUI until Phase 7 succeeds.
- Document migration caveats in release notes prior to rollout.
