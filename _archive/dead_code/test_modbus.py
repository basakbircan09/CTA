from pymodbus.client import ModbusSerialClient

client = ModbusSerialClient(
    port="COM4",
    baudrate=115200,
    parity="N",
    stopbits=1,
    bytesize=8,
    timeout=1
)

print("Connecting:", client.connect())

# SAFE: set speed = 0 rpm
resp = client.write_register(0x0000, 0, device_id=1)
print("Write speed response:", resp)

client.close()
