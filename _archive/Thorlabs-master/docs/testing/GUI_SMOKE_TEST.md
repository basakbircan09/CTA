# GUI Smoke Test

After building the integrated controller, prefer exercising the new entry point. Keep the legacy demos as fallbacks.

1. Activate the environment:
   ```powershell
   cd C:\Users\go97mop\PycharmProjects\Thorlabs
   .\.venv\Scripts\activate
   ```
2. Ensure the ThorCam DLL folder is on `PATH` (see `HARDWARE_TEST.md`).
3. Launch the integrated application:
   ```powershell
   python -m app.main
   ```
   - Verify live view starts/stops, exposure/gain controls respond, the focus bar updates, and snapshots appear in `snapshots/`.
   - The preset manager is currently hidden; preset JSON files can still be managed manually if needed.
4. If troubleshooting is needed, the legacy demos remain available:
   ```powershell
   python scripts\demo_basic.py
   python scripts\demo_white_balance.py
   ```

Log observations (FPS, color balance, errors) in the deployment notes before moving to the next phase.
