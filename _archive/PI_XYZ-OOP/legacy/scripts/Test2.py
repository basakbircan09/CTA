import os
import sys
import time

# The DLL path is still necessary if automatic discovery fails.
# This points to the folder containing the required PI_GCS2_DLL files.
DLL_DIR = r'C:\Program Files (x86)\Physik Instrumente (PI)\Software Suite\Development\C++\API'

os.environ['PATH'] = DLL_DIR + os.pathsep + os.environ.get('PATH', '')

try:
    from pipython import GCSDevice
except Exception as e:
    print(f"Failed to load PI DLL. Check path and Python architecture (32/64-bit).")
    print(f"Original error: {e}")
    sys.exit(1)

# --- MODIFICATION BASED ON IT's SUGGESTION ---
# Define the connection parameters for your X-axis controller
# ... (all the setup code remains the same) ...

COM_PORT = 4
BAUD_RATE = 115200
AXIS = '1'  # It's good practice to define the axis
MOVE_DISTANCE = 10.0  # Define the move distance (e.g., 10 mm)


def main():
    try:
        with GCSDevice() as dev:
            print(f"Connecting to COM{COM_PORT}...")
            dev.ConnectRS232(comport=COM_PORT, baudrate=BAUD_RATE)
            print(f"Connected to: {dev.qIDN().strip()}")

            # --- Motion Sequence ---
            print(f"Enabling servo on axis {AXIS}...")
            dev.SVO(AXIS, 1)

            print(f"Moving axis {AXIS} by {MOVE_DISTANCE} units...")
            dev.MVR(AXIS, MOVE_DISTANCE)

            # Wait for the move to complete. This is very important!
            dev.waitontarget()
            print("Move forward complete. Current position:", dev.qPOS(AXIS)[AXIS])

            time.sleep(1)  # Pause for a second

            print(f"Moving axis {AXIS} back by {-MOVE_DISTANCE} units...")
            dev.MVR(AXIS, -MOVE_DISTANCE)
            dev.waitontarget()
            print("Move back complete. Current position:", dev.qPOS(AXIS)[AXIS])

            print(f"Disabling servo on axis {AXIS}...")
            dev.SVO(AXIS, 0)
            # --- End of Motion Sequence ---

            print("\nTest completed successfully.")

    except Exception as e:
        print(f"\nAN ERROR OCCURRED: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()