#!/usr/bin/python
# -*- coding: utf-8 -*-
"""This example helps you to get used to PIPython."""

# (c)2016 Physik Instrumente (PI) GmbH & Co. KG
# ... (license text remains the same) ...

from pipython import GCSDevice, pitools

__signature__ = 0x986c0f898592ce476e1c88820b09bf94

CONTROLLERNAME = 'C-663.12'
STAGES = None
REFMODES = 'FNL'  # 'FNL' is correct for homing a single, unobstructed stage.


def main():
    """Connect, setup system and move stage to display its position."""
    with GCSDevice('C-663.12') as pidevice:
        pidevice.ConnectUSB(serialnum='025550131')
        print('connected: {}'.format(pidevice.qIDN().strip()))
        if pidevice.HasqVER():
            print('version info:\n{}'.format(pidevice.qVER().strip()))

        print('initialize connected stages...')
        pitools.startup(pidevice, stages=STAGES, refmodes=REFMODES)

        # The following lines that query the soft limits are kept for diagnostic purposes,
        # but we will NOT move to them.
        rangemin = pidevice.qTMN()
        rangemax = pidevice.qTMX()
        print(f"Controller's configured soft limits are Min: {rangemin}, Max: {rangemax}")

        # -------------------------------------------------------------------------
        # MINIMAL REVISION FOR SAFETY
        # The original loop that moved to the potentially unsafe soft limits is
        # commented out below. This is the part that caused your stage to crash.
        #
        # for axis in pidevice.axes:
        #     for target in (rangemin[axis], rangemax[axis]):
        #         print('move axis {} to {:.2f}'.format(axis, target))
        #         pidevice.MOV(axis, target)
        #         pitools.waitontarget(pidevice, axes=axis)
        #         position = pidevice.qPOS(axis)[axis]
        #         print('current position of axis {} is {:.2f}'.format(axis, position))
        # -------------------------------------------------------------------------

        # REPLACEMENT: A single, safe relative move to prove the system works.
        # MVR (Move Relative) is safe because it doesn't rely on pre-configured limits.
        if pidevice.axes:
            axis_to_move = pidevice.axes[0]  # Automatically selects the first connected axis
            move_distance = 1.0  # A small, safe distance in the positive direction (e.g., 1mm)

            print(f"\nPerforming a safe relative move of {move_distance} on axis '{axis_to_move}'...")
            pidevice.MVR(axis_to_move, move_distance)
            pitools.waitontarget(pidevice, axes=axis_to_move)

            position = pidevice.qPOS(axis_to_move)[axis_to_move]
            print('Move complete. Current position of axis {} is {:.4f}'.format(axis_to_move, position))

        print('done')


if __name__ == '__main__':
    main()