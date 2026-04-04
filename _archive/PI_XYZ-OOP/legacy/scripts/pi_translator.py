#!/usr/bin/python
# -*- coding: utf-8 -*-
"""
A universal translator for pipython scripts. (Compatible for 2.0 and previous Tmotion scripts)

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
        # UPDATED: Provide a default axis, as scripts now access it immediately after connection.
        self.axes = ['1']
        self.positions = {'1': 0.0}
        self.velocities = {'1': 0.0} # NEW: Dictionary to track velocity.
        self._is_connected = False

    def ConnectUSB(self, serialnum):
        PROTOCOL_LOG.append(f"Connect to controller via USB (Serial: {serialnum}).")
        self._is_connected = True

    def IsConnected(self):
        return self._is_connected

    def CloseConnection(self):
        PROTOCOL_LOG.append("Close connection to controller.")
        self._is_connected = False

    # --- UPDATED & NEW Simulator Methods ---
    def SVO(self, axis, state):
        """UPDATED: Simulate setting Servo state and log it."""
        PROTOCOL_LOG.append(f"Set servo for axis '{axis}' to {'ON' if state else 'OFF'}.")

    def CST(self, axis, stage):
        """UPDATED: Simulate configuring a stage and log it."""
        PROTOCOL_LOG.append(f"Configure stage '{stage}' for axis '{axis}'.")

    def FPL(self, axis):
        """UPDATED: Simulate Find Positive Limit reference move and log it."""
        PROTOCOL_LOG.append(f"Begin referencing move ('FPL') for axis '{axis}'.")
        self.positions[str(axis)] = 0.0 # Referencing resets the logical position.

    def MVR(self, axis, distance):
        """NEW: Simulate a relative move."""
        PROTOCOL_LOG.append(f"Move axis '{axis}' by a relative distance of {distance:.3f} mm.")
        # Correctly update the position based on the relative move.
        current_pos = self.positions.get(str(axis), 0.0)
        self.positions[str(axis)] = current_pos + float(distance)

    def VEL(self, axis, velocity):
        """NEW: Simulate setting the velocity."""
        PROTOCOL_LOG.append(f"Set velocity for axis '{axis}' to {velocity:.2f} mm/s.")
        self.velocities[str(axis)] = float(velocity)

    def qVEL(self, axis):
        """NEW: Simulate querying the velocity."""
        # This just returns the value we stored from the last VEL command.
        return {str(axis): self.velocities.get(str(axis), 0.0)}
    # --- End of Method Updates ---

    def qIDN(self):
        return "Simulated E-880 GCS3.0 Controller"

    def MOV(self, axis, target):
        PROTOCOL_LOG.append(f"Move axis '{axis}' to absolute position {target:.3f} mm.")
        self.positions[str(axis)] = float(target)

    def qPOS(self, axis=None):
        if axis:
            return {str(axis): self.positions.get(str(axis), 0.0)}
        return self.positions

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.CloseConnection()


def patch_pipython_for_translation():
    """Replaces the GCSDevice class and pitools module with our simulators."""
    import pipython

    mock_pitools = MagicMock()

    def spy_waitontarget(pidevice, axes=None, **kwargs):
        wait_axes = axes if axes is not None else pidevice.axes
        PROTOCOL_LOG.append(f"  - Wait for move on axes {wait_axes} to complete.")

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