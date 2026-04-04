# OOP Refactor - Documentation Index

This directory now holds the streamlined references required to build the new object-oriented control system.

## Document Map

| File | Purpose |
| --- | --- |
| [ARCHITECTURE.md](ARCHITECTURE.md) | High-level blueprint detailing layering rules, migration strategy, and success metrics |
| [INTERFACES.md](INTERFACES.md) | Formal API contracts for models, hardware adapters, services, and GUI controllers |
| [IMPLEMENTATION_PLAN.md](IMPLEMENTATION_PLAN.md) | Phased build order with dependencies, acceptance criteria, and realistic effort estimates |
| [APPENDICES.md](APPENDICES.md) | Source trace map, spike instructions, glossary, risk register, and sign-off checklist |

## How to Use This Set
1. **Orient:** read `ARCHITECTURE.md` once to understand constraints and guiding principles.
2. **Implement:** pick tasks from `IMPLEMENTATION_PLAN.md`; cross-check method signatures in `INTERFACES.md` while coding.
3. **Validate:** execute spikes and tests, then record results in `APPENDICES.md` so decisions stay auditable.
4. **Review:** keep stakeholders aligned by reviewing the risk log and checklist in `APPENDICES.md`.

Legacy seven-part documents have been superseded by this concise collection. Refer to repository history if you need the original long-form drafts.
