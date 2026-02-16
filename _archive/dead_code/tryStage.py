from pipython import GCSDevice

# List all connected USB devices
with GCSDevice() as pi:
    devices = pi.EnumerateUSB()
    print("Connected devices:")
    for dev in devices:
        print(f"  {dev}")
