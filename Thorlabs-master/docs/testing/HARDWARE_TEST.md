# Hardware Verification Checklist

Use this short checklist after code changes to confirm the real CS165CU camera
still connects and streams correctly. These steps should be executed on a
workstation with the camera attached and the ThorCam toolkit installed.

1. **Activate environment**
   ```powershell
   cd C:\Users\go97mop\PycharmProjects\Thorlabs
   .\.venv\Scripts\activate
   ```

2. **Expose Thorlabs DLLs** (skip if already in `PATH`).
   ```powershell
   $env:PATH = "$PWD\ThorCam;$env:PATH"
   ```

3. **Run the adapter smoke test**
   ```powershell
   python scripts\check_camera.py
   ```
   Expected output:
   - SDK initializes without errors
   - Camera serial numbers are listed
   - A single frame is acquired successfully

4. **Capture live preview (optional)**
   ```powershell
   python scripts\demo_basic.py
   ```
   Confirm that the live view updates and exposure/gain controls respond.

5. **Record results**
   - If every step passes, mark the deployment log with “Hardware OK”.
   - If any step fails, capture the console output and open an issue before
     merging further changes.

This checklist complements the automated unit tests. Run it whenever the device
adapter or acquisition pipeline changes, or before tagging a release.
