#!/usr/bin/python
# -*- coding: utf-8 -*-
"""
A universal translator for pipython scripts.

This script loads a user-provided pipython script, intercepts all hardware
commands by patching the correct internal classes, and generates a
human-readable protocol log.

THE TARGET SCRIPT REMAINS UNMODIFIED.

Usage:
    python run_and_translate.py <path_to_your_script.py>
"""

import sys
import runpy
from datetime import datetime

# This list will store our human-readable protocol steps.
PROTOCOL_LOG = []


def patch_pipython_for_translation():
    """
    Replaces real pipython functions with spy functions that log actions.
    This version targets the correct internal classes based on pipython's structure.
    """
    # We must import the specific internal modules we intend to patch.
    from pipython.pidevice.common import gcsbasedevice
    from pipython import pitools

    print("--- PIPython hardware commands have been replaced with loggers ---")

    # --- Define Spy Functions ---
    # These functions will replace the real hardware-interacting methods.

    def spy_connect_usb(self, serialnum):
        PROTOCOL_LOG.append(f"Connect to controller via USB (Serial: {serialnum}).")
        # The real object would initialize 'axes'. We must simulate it here.
        if not hasattr(self, '_axes'):
            self._axes = ['1']  # Default to one axis for simplemove.py

    def spy_qIDN(self):
        return "Simulated C-663.12 Controller"

    def spy_qTMN(self):
        PROTOCOL_LOG.append("Querying minimum travel limits.")
        return {axis: 0.0 for axis in self.axes}

    def spy_qTMX(self):
        PROTOCOL_LOG.append("Querying maximum travel limits.")
        return {axis: 200.0 for axis in self.axes}

    def spy_mov(self, axis, target):
        PROTOCOL_LOG.append(f"Move axis '{axis}' to absolute position {target:.3f} mm.")

    def spy_qPOS(self, axis=None):
        # Return a plausible dummy value to prevent errors in the user script.
        return {axis: -1.0} if axis else {'1': -1.0}

    def spy_axes_getter(self):
        """Simulates the 'axes' property."""
        return self._axes

    def spy_startup(pidevice, stages=None, refmodes=None):
        ref_str = refmodes if isinstance(refmodes, str) else ', '.join(refmodes)
        PROTOCOL_LOG.append(f"Initialize and reference stages using mode(s): {ref_str}.")
        # After startup, the number of axes is known. Let's adjust our mock.
        if stages:
            pidevice._axes = [str(i + 1) for i in range(len(stages))]

    def spy_waitontarget(pidevice, axes=None):
        PROTOCOL_LOG.append(f"  - Wait for move on axis '{axes}' to complete.")

    # --- Apply the Patches to the CORRECT Classes ---
    gcsbasedevice.GCSBaseDevice.ConnectUSB = spy_connect_usb
    gcsbasedevice.GCSBaseDevice.qIDN = spy_qIDN
    gcsbasedevice.GCSBaseDevice.qTMN = spy_qTMN
    gcsbasedevice.GCSBaseDevice.qTMX = spy_qTMX
    gcsbasedevice.GCSBaseDevice.MOV = spy_mov
    gcsbasedevice.GCSBaseDevice.qPOS = spy_qPOS

    # Patch the 'axes' property getter
    gcsbasedevice.GCSBaseDevice.axes = property(spy_axes_getter)

    # Patch the standalone functions in the pitools module
    pitools.startup = spy_startup
    pitools.waitontarget = spy_waitontarget


def generate_report(script_name):
    """Formats and prints the human-readable protocol."""
    report = [
        "\n" + "=" * 60,
        "   Human-Readable Motion Protocol Translation",
        "=" * 60,
        f"Protocol Source File: {script_name}",
        f"Translation Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
        "-" * 60,
        "\nSummary of Operations:\n"
    ]
    step_num = 1
    for line in PROTOCOL_LOG:
        if not line.strip().startswith('-'):
            report.append(f"{step_num}. {line}")
            step_num += 1
        else:
            report.append(line)

    report.extend(["\n" + "=" * 60, "           End of Translation", "=" * 60])
    return "\n".join(report)


def main():
    """Main function to patch, run the user's script, and report the log."""
    if len(sys.argv) < 2:
        print("ERROR: Please provide the path to the protocol script to translate.")
        print("Usage: python run_and_translate.py simplemove.py")
        sys.exit(1)

    protocol_filepath = sys.argv[1]

    patch_pipython_for_translation()

    print(f"\n--- Translating script: {protocol_filepath} ---\n")
    try:
        runpy.run_path(protocol_filepath, run_name='__main__')
    except Exception as e:
        print(f"\n--- An error occurred during script execution ---")
        print(f"ERROR: {e}")
        print("--- The protocol below shows the steps taken before the error ---")

    report = generate_report(protocol_filepath)
    print(report)


if __name__ == '__main__':
    main()