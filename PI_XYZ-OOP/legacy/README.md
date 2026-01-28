# Legacy Assets

This directory preserves the original procedural tooling and GUI that shipped on the `master` branch. They remain available for reference and fallback while the new object-oriented architecture in `PI_Control_System/` is developed.

## Contents

- `PI_Control_GUI/` – Existing PySide6 application and hardware controller.
- `noGUI/` – Vendor DLLs and libraries required by the legacy scripts.
- `scripts/` – Original standalone motion/control utilities (`Tmotion2.0.py`, `simplemove.py`, translators, etc.).

## Usage

Nothing in this directory is imported by the new OOP code path. Keep the legacy code untouched unless you are specifically maintaining the old tooling. The new architecture should live exclusively under `PI_Control_System/`.
