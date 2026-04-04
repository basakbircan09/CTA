#!/usr/bin/python
# -*- coding: utf-8 -*-
"""
A universal translator for pipython scripts.

This script loads a user-provided pipython script, intercepts all hardware
commands by providing a complete, robust mock object, and generates a
human-readable protocol log.

THE TARGET SCRIPT REMAINS UNMODIFIED.

Usage:
    python pi_translator.py <path_to_your_script.py>
"""

import sys
import runpy
from datetime import datetime
from unittest.mock import MagicMock

# This list will store our human-readable protocol steps.
PROTOCOL_LOG = []


class PISimulator:
    """A robust, self-contained simulator for a PI GCSDevice."""

    def __init__(self, *args, **kwargs):
        """Initializes the simulated device."""
        self.axes = []  # MODIFIED: Start with no axes; startup will define them.
        self.positions = {}  # ADDED: Dictionary to track the position of each axis.
        self._is_connected = False  # ADDED: Flag to track connection status.

    def ConnectUSB(self, serialnum):
        PROTOCOL_LOG.append(f"Connect to controller via USB (Serial: {serialnum}).")
        self._is_connected = True  # ADDED: Set connection status.

    def ConnectTCPIP(self, ipaddress, ipport=50000):
        PROTOCOL_LOG.append(f"Connect to controller via TCP/IP (IP: {ipaddress}).")
        self._is_connected = True  # ADDED: Set connection status.

    # --- ADDED Missing Methods ---
    def IsConnected(self):
        """ADDED: Method required by the user's script for cleanup."""
        return self._is_connected

    def CloseConnection(self):
        """ADDED: Method required by the user's script for cleanup."""
        PROTOCOL_LOG.append("Close connection to controller.")
        self._is_connected = False

    # ADDED: Placeholder methods for pitools.startup to call without error.
    def SVO(self, *args, **kwargs): pass

    def CST(self, *args, **kwargs): pass

    def FPL(self, *args, **kwargs): pass

    # --- End of ADDED Methods ---

    def qIDN(self):
        return "Simulated E-880 GCS3.0 Controller"

    def MOV(self, axis, target):
        PROTOCOL_LOG.append(f"Move axis '{axis}' to absolute position {target:.3f} mm.")
        self.positions[str(axis)] = float(target)  # MODIFIED: Update the stored position.

    def qPOS(self, axis=None):
        return self.positions  # MODIFIED: Return the actual stored position.

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.CloseConnection()  # MODIFIED: Ensure connection is closed if using 'with' statement.

    # NOTE: qSPV and qVER methods were removed as they are not used by your script.


def patch_pipython_for_translation():
    """Replaces the GCSDevice class and pitools module with our simulators."""
    import pipython

    mock_pitools = MagicMock()

    def spy_startup(pidevice, stages=None, refmodes=None, **kwargs):
        ref_str = refmodes if isinstance(refmodes, str) else ', '.join(refmodes or [])
        PROTOCOL_LOG.append(f"Initialize and reference stages using mode(s): {ref_str}.")

        # Determine axes from provided arguments.
        if stages:
            pidevice.axes = [str(i + 1) for i in range(len(stages))]
        elif refmodes:
            pidevice.axes = [str(i + 1) for i in range(len(refmodes))]

        # ADDED: Initialize axis positions to 0.0 after referencing.
        for axis in pidevice.axes:
            pidevice.positions[axis] = 0.0

    def spy_waitontarget(pidevice, axes=None, **kwargs):
        # MODIFIED: Intelligently log which axes are being waited on.
        wait_axes = axes if axes is not None else pidevice.axes
        PROTOCOL_LOG.append(f"  - Wait for move on axes {wait_axes} to complete.")

    mock_pitools.startup = spy_startup
    mock_pitools.waitontarget = spy_waitontarget

    pipython.GCSDevice = PISimulator
    pipython.pitools = mock_pitools

    print("--- PIPython has been replaced with the translation simulator ---")


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
        print("Usage: python pi_translator.py <your_script.py>")
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