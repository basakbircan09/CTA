"""
Pixel-to-stage alignment calculations for the SFC automation system.

Converts manually selected spot pixel coordinates (from ManualSpotDialog)
into absolute stage XY targets, then produces ordered motion sequences that
respect all Z-safety rules:

  1. Never move Z downward before XY alignment is complete.
  2. Always raise Z before moving between spots.
  3. Always stop at SFC_Z + Z_APPROACH_OFFSET (default +5 mm) before contact.
  4. Never go directly from spot-to-spot without lifting Z.
"""

from __future__ import annotations

from dataclasses import dataclass

# ---------------------------------------------------------------------------
# Calibration constant
# ---------------------------------------------------------------------------

PIXEL_SCALE_MM: float = 0.094  # mm per pixel (fixed, factory-calibrated)


# ---------------------------------------------------------------------------
# Data types
# ---------------------------------------------------------------------------

@dataclass
class AlignmentResult:
    """Computed alignment data for a single spot."""
    label: str
    pixel_pos: tuple[int, int]           # absolute pixel position (x, y)
    pixel_offset: tuple[int, int]        # (dx, dy) relative to Reference pixel
    real_offset_mm: tuple[float, float]  # pixel_offset converted to mm (with axis inversion)
    stage_move_mm: tuple[float, float]   # delta stage movement from base position


@dataclass
class MotionStep:
    """One atomic stage move in a motion sequence."""
    description: str
    target_x: float
    target_y: float
    target_z: float


# ---------------------------------------------------------------------------
# Aligner
# ---------------------------------------------------------------------------

class SpotAligner:
    """Convert pixel spot coordinates to stage movement commands.

    Parameters
    ----------
    holder_to_sfc_x, holder_to_sfc_y : float
        Mechanical distance (mm) from the holder reference corner to the SFC
        opening in X and Y.
    sfc_z : float
        Absolute Z coordinate (mm) of the SFC opening.
    pixel_scale : float
        mm per pixel.  Default: PIXEL_SCALE_MM (0.094).
    invert_x, invert_y : bool
        Flip axis direction to reconcile camera vs stage coordinate systems.
        Camera: x increases rightward, y increases downward.
        Stage:  X decreases going right, Y decreases going upward.
        Both default to True (both axes inverted).
    """

    Z_RAISE_MM:        float = 20.0  # mm to lift Z when moving between spots
    Z_APPROACH_OFFSET: float =  5.0  # mm above SFC Z at which to stop

    def __init__(
        self,
        holder_to_sfc_x: float,
        holder_to_sfc_y: float,
        sfc_z: float,
        pixel_scale: float = PIXEL_SCALE_MM,
        invert_x: bool = True,
        invert_y: bool = True,
    ) -> None:
        self.holder_to_sfc_x = holder_to_sfc_x
        self.holder_to_sfc_y = holder_to_sfc_y
        self.sfc_z           = sfc_z
        self.pixel_scale     = pixel_scale
        self.invert_x        = invert_x
        self.invert_y        = invert_y

        self._reference: dict | None = None
        self._spots: list[dict]      = []

    # ------------------------------------------------------------------
    # Data loading
    # ------------------------------------------------------------------

    def load_spots(self, reference: dict, spots: list[dict]) -> None:
        """Load reference and spot dicts from ManualSpotDialog output."""
        if reference is None:
            raise ValueError("A Reference pixel must be marked before loading spots.")
        self._reference = reference
        self._spots     = list(spots)

    @property
    def spot_labels(self) -> list[str]:
        return [s["label"] for s in self._spots]

    # ------------------------------------------------------------------
    # Alignment computation
    # ------------------------------------------------------------------

    def compute_alignment(self, spot_label: str) -> AlignmentResult:
        """Return the AlignmentResult for a single named spot."""
        self._require_loaded()
        spot = next((s for s in self._spots if s["label"] == spot_label), None)
        if spot is None:
            raise ValueError(
                f"Spot '{spot_label}' not found. "
                f"Available: {self.spot_labels}"
            )
        return self._compute(spot)

    def compute_all_alignments(self) -> list[AlignmentResult]:
        """Return AlignmentResults for all loaded spots, in order."""
        self._require_loaded()
        return [self._compute(s) for s in self._spots]

    def stage_target(
        self,
        result: AlignmentResult,
        base_x: float,
        base_y: float,
    ) -> tuple[float, float]:
        """Absolute stage XY target given a base reference stage position.

        base_x/base_y is the stage position when the image was captured
        (i.e. the position at which the Reference pixel was aligned to the
        physical reference corner of the holder).
        """
        return (
            round(base_x + result.stage_move_mm[0], 3),
            round(base_y + result.stage_move_mm[1], 3),
        )

    # ------------------------------------------------------------------
    # Motion sequences
    # ------------------------------------------------------------------

    def first_spot_sequence(
        self,
        target_x: float,
        target_y: float,
        current_x: float,
        current_y: float,
        current_z: float,
        label: str = "",
    ) -> list[MotionStep]:
        """Motion steps for reaching the very first spot from any position.

        Rule: move XY first (at current Z), then lower Z to SFC_Z + offset.
        Never lower Z before XY is done.
        """
        z_final = self.sfc_z + self.Z_APPROACH_OFFSET
        return [
            MotionStep(
                description=f"[{label}] Move XY to alignment position",
                target_x=target_x,
                target_y=target_y,
                target_z=current_z,          # keep Z unchanged during XY move
            ),
            MotionStep(
                description=f"[{label}] Lower Z to SFC approach height ({z_final:.1f} mm)",
                target_x=target_x,
                target_y=target_y,
                target_z=z_final,
            ),
        ]

    def between_spot_sequence(
        self,
        target_x: float,
        target_y: float,
        current_x: float,
        current_y: float,
        current_z: float,
        label: str = "",
    ) -> list[MotionStep]:
        """Motion steps for moving from one spot to the next.

        Rule: raise Z first, then move XY, then lower Z.
        """
        z_raised = current_z + self.Z_RAISE_MM
        z_final  = self.sfc_z + self.Z_APPROACH_OFFSET
        return [
            MotionStep(
                description=f"[{label}] Raise Z by {self.Z_RAISE_MM:.0f} mm (collision avoidance)",
                target_x=current_x,
                target_y=current_y,
                target_z=z_raised,
            ),
            MotionStep(
                description=f"[{label}] Move XY to alignment position",
                target_x=target_x,
                target_y=target_y,
                target_z=z_raised,           # XY at raised Z
            ),
            MotionStep(
                description=f"[{label}] Lower Z to SFC approach height ({z_final:.1f} mm)",
                target_x=target_x,
                target_y=target_y,
                target_z=z_final,
            ),
        ]
