import pymodbus
import inspect
from pymodbus.client import ModbusSerialClient

print("pymodbus version:", pymodbus.__version__)
print("write_register signature:")
print(inspect.signature(ModbusSerialClient.write_register))
