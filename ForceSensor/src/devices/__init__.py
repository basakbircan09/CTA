"""
GOED Device Abstraction Layer

Provides unified interface for all devices. Process isolation via wrapper
subprocess is the target architecture for all devices to avoid USB/DLL conflicts.

Current Status (native branch - Phase 8):
- ThorlabsDevice: Native (temporary, being migrated to wrapper)
- ThorlabsWrapperDevice: Wrapper for process isolation (Phase 8 WP1)
- GamryDevice: Wrapper via SupervisorService (Python 3.7-32 requirement)
- PI XYZ: Wrapper via SupervisorService (USB conflict with Thorlabs)

Usage:
    from devices import DeviceRegistry, ThorlabsWrapperDevice

    registry = DeviceRegistry()
    registry.register(ThorlabsWrapperDevice(config))

    device = registry.get("thorlabs")
    device.execute_async("snapshot", {"output_path": "snapshot.png"})
"""

from devices.base import (
    Device,
    DeviceState,
    DeviceInfo,
    CommandResult,
    CommandCallback,
)
from devices.registry import DeviceRegistry
from devices.thread_safe_device import ThreadSafeDevice
from devices.thorlabs_device import ThorlabsDevice
from devices.thorlabs_wrapper_device import ThorlabsWrapperDevice
from devices.gamry_device import GamryDevice
from devices.pi_wrapper_device import PIWrapperDevice
from devices.perimax_wrapper_device import PerimaxWrapperDevice
from devices.force_wrapper_device import ForceWrapperDevice

__all__ = [
    # Base classes
    "Device",
    "DeviceState",
    "DeviceInfo",
    "CommandResult",
    "CommandCallback",
    # Thread-safe base
    "ThreadSafeDevice",
    # Device implementations
    "ThorlabsDevice",           # Native (temporary)
    "ThorlabsWrapperDevice",    # Wrapper-based (Phase 8)
    "GamryDevice",              # Wrapper-based
    "PIWrapperDevice",          # Wrapper-based (Section 9 migration)
    "PerimaxWrapperDevice",     # Wrapper-based (Perimax pump)
    "ForceWrapperDevice",       # Wrapper-based (I-7016 force sensor)
    # Registry
    "DeviceRegistry",
]
