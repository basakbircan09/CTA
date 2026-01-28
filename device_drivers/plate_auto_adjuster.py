# device_drivers/plate_auto_adjuster.py

from __future__ import annotations

from pathlib import Path
from typing import Tuple, List

from device_drivers.plate_finder import gray_plate_on_red
from device_drivers.thorlabs_camera_wrapper import ThorlabsCamera
from device_drivers.PI_Control_System.core.models import Axis, Position
from device_drivers.PI_Control_System.services.motion_service import MotionService


def auto_adjust_plate(
    motion_service: MotionService,
    camera: ThorlabsCamera,
    save_dir: Path,
    step_mm: float = 5.0,
    max_iterations: int = 10,
) -> Tuple[bool, str, List[str]]:
    """
    Auto-adjust stage to bring plate fully into frame.

    Returns:
        fully_in_frame, final_hint, log_messages
    """
    log: List[str] = []
    save_dir.mkdir(parents=True, exist_ok=True)

    for i in range(1, max_iterations + 1):
        img_path = save_dir / f"auto_adjust_{i}.png"

        # 1) capture frame
        frame = camera.save_frame(str(img_path))
        log.append(f"[iter {i}] Captured {img_path}")

        # 2) run plate finder
        result = gray_plate_on_red(str(img_path), margin_frac=0.02, debug=False)
        fully = result["fully_in_frame"]
        hint = result["move_hint"]
        log.append(f"[iter {i}] fully_in_frame={fully}, hint={hint}")

        if fully:
            log.append(f"[iter {i}] Plate is fully in frame. Done.")
            return True, hint, log

        # 3) decide move based on hint
        # Map image-based hint to stage relative move (X,Y,Z)
        dx = dy = 0.0

        # NOTE: You may need to invert directions depending on your optics.
        if "left" in hint:
            dx = step_mm    # move stage +X
        elif "right" in hint:
            dx = -step_mm   # move stage -X

        if "up" in hint:
            dy = step_mm    # move stage +Y
        elif "down" in hint:
            dy = -step_mm   # move stage -Y

        if dx == 0 and dy == 0:
            # hint is 'no_plate', 'no_red', 'adjust', or unknown
            log.append(f"[iter {i}] No clear direction from hint='{hint}'. Stopping.")
            return False, hint, log

        # 4) execute move: relative move in X/Y, keep Z unchanged
        rel_pos = Position(x=dx, y=dy, z=0.0)
        fut = motion_service.move_to_position(
            # Use current position + relative? MotionService currently does absolute moves,
            # so instead use per-axis relative moves:
            # Here we just call move_axis_relative for X and Y.
            position=None  # placeholder; we'll not use this route
        )
        # BUT MotionService already has move_axis_relative, so better:
        motion_service.move_axis_relative(Axis.X, dx)
        motion_service.move_axis_relative(Axis.Y, dy)
        # Wait is handled by those calls internally via executor.

        log.append(f"[iter {i}] Requested stage move: ΔX={dx} mm, ΔY={dy} mm")

    # If we exit loop without success
    log.append("Max iterations reached without fully in frame.")
    return False, hint, log
