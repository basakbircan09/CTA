#!/usr/bin/python
# -*- coding: utf-8 -*-
"""
This script demonstrates how to generate a human-readable protocol from a
motion script, suitable for chemists, material scientists, and lab notebooks.

It uses a "Protocol Generator" class to wrap hardware commands, which both
builds the protocol log and executes the commands.
"""

from pipython import GCSDevice, pitools, GCSError

# (c)2024 Physik Instrumente (PI) GmbH & Co. KG

__signature__ = 0x0123456789abcdef

# --- CONFIGURATION ---
# Set to True to generate the protocol without moving hardware.
# Set to False to run on hardware AND generate the protocol.
DRY_RUN = True

# -- Your Hardware Configuration --
CONTROLLERNAME = 'C-663.12'
STAGES = ['62309260', '62309260', '62309260']  # 3x VT-80 200mm
REFMODES = ['FPL', 'FPL', 'FPL']  # Find Positive Limit


# MOCK DEVICE for DRY_RUN mode (from previous example)
class MockGCSDevice:
    """A mock GCSDevice class that simulates hardware for a dry run."""

    def __init__(self, devname=''):
        self.axes = ['1', '2', '3']
        self._positions = {axis: 200.0 for axis in self.axes}  # Start at FPL

    def __enter__(self): return self

    def __exit__(self, exc_type, exc_val, exc_tb): pass

    def ConnectUSB(self, serialnum): pass

    def qIDN(self): return "SIMULATED C-663.12\n"

    def qTMN(self): return {axis: 0.0 for axis in self.axes}

    def qTMX(self): return {axis: 200.0 for axis in self.axes}

    def MOV(self, axis, target): self._positions[axis] = target

    def qPOS(self, axis=None): return {axis: self._positions[axis]}


class MotionProtocolGenerator:
    """Wraps pipython commands to generate a human-readable protocol."""

    def __init__(self, pidevice, dry_run=False):
        """
        Initializes the protocol generator.
        Args:
            pidevice: An instantiated and connected GCSDevice (or mock device).
            dry_run (bool): If True, will not send commands to hardware.
        """
        self.pidevice = pidevice
        self.dry_run = dry_run
        self.steps = []
        self.step_counter = 1

    def initialize_stages(self, stages, refmodes):
        """Protocol step for initializing and referencing stages."""
        log_entry = f"Initialize and reference all stages. Using reference mode(s): {', '.join(refmodes)}."
        print(f"INFO: {log_entry}")
        self.steps.append(log_entry)
        if not self.dry_run:
            pitools.DeviceStartup(self.pidevice, stages=stages, refmodes=refmodes).run()

    def move_absolute(self, axis, target):
        """Protocol step for an absolute move."""
        log_entry = f"Move axis '{axis}' to absolute position {target:.3f} mm."
        print(f"INFO: Executing Step {self.step_counter}: {log_entry}")
        self.steps.append(log_entry)

        if not self.dry_run:
            self.pidevice.MOV(axis, target)
            pitools.waitontarget(self.pidevice, axes=axis)

        self.step_counter += 1
        # In a real scenario, you could add a verification step here.
        self._verify_position(axis)

    def _verify_position(self, axis):
        """Internal step to log the position verification."""
        log_entry = f"  - Verify: Confirm axis '{axis}' has reached the target position."
        self.steps.append(log_entry)
        if not self.dry_run:
            pos = self.pidevice.qPOS(axis)[axis]
            self.steps.append(f"    - Hardware confirmation: Position is {pos:.3f} mm.")

    def generate_report(self):
        """Formats and returns the final human-readable protocol."""
        report = []
        report.append("\n" + "=" * 50)
        report.append("   Human-Readable Motion Protocol Report")
        report.append("=" * 50)
        report.append(f"Generated on: 2025-08-25 11:51")
        report.append(f"Controller: {CONTROLLERNAME}")
        report.append(f"Stages: {', '.join(STAGES)}")
        report.append("-" * 50)
        report.append("\nSummary of Operations:\n")

        step_num = 1
        for line in self.steps:
            if not line.strip().startswith('-'):
                report.append(f"{step_num}. {line}")
                step_num += 1
            else:
                report.append(line)

        report.append("\n" + "=" * 50)
        report.append("           End of Protocol")
        report.append("=" * 50)
        return "\n".join(report)


def main():
    """Main function to define and execute the motion protocol."""
    pidevice = MockGCSDevice(CONTROLLERNAME) if DRY_RUN else GCSDevice(CONTROLLERNAME)

    with pidevice:
        if not DRY_RUN:
            pidevice.ConnectUSB(serialnum='025550143')

        # Create an instance of our protocol generator
        protocol = MotionProtocolGenerator(pidevice, dry_run=DRY_RUN)

        # --- Define Your Motion Protocol Using the Generator ---

        # Step 1: Initialize
        protocol.initialize_stages(STAGES, REFMODES)

        # Get limits for defining movements
        rangemin = pidevice.qTMN()
        rangemax = pidevice.qTMX()

        # Step 2: Main movement sequence
        for axis in pidevice.axes:
            # Move to a position 30 mm from the minimum
            protocol.move_absolute(axis, rangemin[axis] + 30)

            # Move to a position 20 mm from the maximum
            protocol.move_absolute(axis, rangemax[axis] - 20)

        # --- Protocol Finished ---

        # Print the final, formatted report
        report_output = protocol.generate_report()
        print(report_output)


if __name__ == '__main__':
    main()