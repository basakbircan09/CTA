from pymodbus.client import ModbusSerialClient
import time

PORT = "COM4"   # change if her adapter is on a different COM port
DEV  = 1        # pump address (DIP switches)

client = ModbusSerialClient(
    port=PORT,
    baudrate=115200,
    parity="N",
    stopbits=1,
    bytesize=8,
    timeout=1
)

ok = client.connect()
print("Connecting:", ok)
if not ok:
    raise RuntimeError(f"Could not open {PORT}. Check USB adapter / COM port.")

def wr(reg, val):
    r = client.write_register(reg, val, device_id=DEV)
    print(f"WR 0x{reg:04X} <- {val} :", r)
    return r

# Stop (safe)
wr(0x0002, 0)

# Direction: 1=CW, 0=CCW
wr(0x0003, 1)

# Speed: rpm * 100  (example: 5 rpm -> 500, 15 rpm -> 1500)
wr(0x0000, 1500)   # 15.00 rpm

# Start
wr(0x0002, 1)

time.sleep(3)

# Stop
wr(0x0002, 0)

client.close()
