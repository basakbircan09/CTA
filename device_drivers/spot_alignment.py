"""
Pixel-to-stage alignment calculations for the SFC automation system.

Converts manually selected spot pixel coordinates (from ManualSpotDialog)
into absolute stage XY targets, then produces ordered motion sequences that
respect all Z-safety rules:

  1. Never move Z downward before XY alignment is complete.
  2. Always raise Z before moving between spots.
  3. Always stop at APPROACH_Z (SFC_Z + 5 mm) — never descend to SFC_Z here.
  4. Never go directly from spot-to-spot without lifting Z.

Lab calibration values (fixed, measured on this machine):
  SFC opening:       X=130.0  Y=17.0   Z=112.0  (absolute stage mm)
  Approach height:   Z=117.0  (= SFC_Z + 5 mm — stop here for contact logic)
  Ref stage position at image capture:  X=224.5  Y=229.5
  Pixel scale:       0.094 mm / pixel
"""

from __future__ import annotations

from dataclasses import dataclass

# ---------------------------------------------------------------------------
# Lab calibration constants  (edit here when physically re-calibrated)
# ---------------------------------------------------------------------------

PIXEL_SCALE_MM: float = 0.094   # mm per pixel

SFC_X: float = 130.0            # absolute stage X of SFC opening
SFC_Y: float =  17.0            # absolute stage Y of SFC opening
SFC_Z: float = 112.0            # absolute stage Z of SFC opening
APPROACH_Z: float = 117.0       # SFC_Z + 5.0 — approach / safe-stop height

REF_STAGE_X: float = 224.5      # stage X when reference image was captured
REF_STAGE_Y: float = 229.5      # stage Y when reference image was captured


# ---------------------------------------------------------------------------
# Data types
# ---------------------------------------------------------------------------

@dataclass
class AlignmentResult:
    """Computed alignment data for a single spot."""
    label: str
    pixel_pos: tuple[int, int]           # absolute pixel position (x, y)
    pixel_offset: tuple[int, int]        # (dx, dy) relative to Reference pixel
    real_offset_mm: tuple[float, float]  # pixel_offset → mm (with axis inversion)
    stage_move_mm: tuple[float, float]   # delta from REF_STAGE to absolute target


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
    """Convert pixel spot coordinates to absolute stage targets.

    Parameters
    ----------
    pixel_scale : float
        mm per pixel.  Default: PIXEL_SCALE_MM (0.094).
    invert_x, invert_y : bool
        Flip axis direction sign for stage X and Y respectively.
        Both default to True.  Keep configurable because camera mounting
        orientation can vary.

    Alignment math
    --------------
    Lab-observed axis mapping (camera image vs stage):
      Image X (horizontal pixel movement) → Stage Y
      Image Y (vertical pixel movement)   → Stage X

    With stage at REF_STAGE (224.5, 229.5) the image is captured.
    The reference marker appears at pixel (x_ref, y_ref); spot at (x_spot, y_spot).

      dx_pixels = x_spot - x_ref
      dy_pixels = y_spot - y_ref

      real_offset_x = sign_x * dy_pixels * pixel_scale   # pixel Y → stage X
      real_offset_y = sign_y * dx_pixels * pixel_scale   # pixel X → stage Y

      where sign_x = -1 if invert_x else +1
            sign_y = -1 if invert_y else +1

    Absolute stage target to place the spot under the SFC opening:

      TARGET_X = REF_STAGE_X - SFC_X - real_offset_x  →  94.5 - real_offset_x
      TARGET_Y = REF_STAGE_Y - SFC_Y - real_offset_y  → 212.5 - real_offset_y
      TARGET_Z = APPROACH_Z                            →  117.0  (never lower in this step)
    """

    Z_RAISE_MM: float = 20.0   # mm to lift Z when moving between spots

    def __init__(
        self,
        pixel_scale: float = PIXEL_SCALE_MM,
        invert_x: bool = True,
        invert_y: bool = False,
    ) -> None:
        self.pixel_scale = pixel_scale
        self.invert_x    = invert_x
        self.invert_y    = invert_y

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

    def stage_target(self, result: AlignmentResult) -> tuple[float, float]:
        """Absolute stage XY target to place this spot under the SFC opening.

        Returns (target_x, target_y) rounded to 3 decimal places.
        """
        tx = round(REF_STAGE_X + result.stage_move_mm[0], 3)
        ty = round(REF_STAGE_Y + result.stage_move_mm[1], 3)
        return tx, ty

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

        Rule: move XY first (at current Z), then lower Z to APPROACH_Z.
        Never lower Z before XY is complete.
        """
        return [
            MotionStep(
                description=f"[{label}] Move XY to alignment position"
                            f"  (target X={target_x:.3f}  Y={target_y:.3f} mm)",
                target_x=target_x,
                target_y=target_y,
                target_z=current_z,          # keep Z unchanged during XY move
            ),
            MotionStep(
                description=f"[{label}] Lower Z to approach height"
                            f"  (Z={APPROACH_Z:.1f} mm — SFC opening at {SFC_Z:.1f} mm)",
                target_x=target_x,
                target_y=target_y,
                target_z=APPROACH_Z,
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

        Rule: raise Z first, then move XY, then lower Z to APPROACH_Z.
        """
        z_raised = current_z + self.Z_RAISE_MM
        return [
            MotionStep(
                description=f"[{label}] Raise Z by {self.Z_RAISE_MM:.0f} mm"
                            f"  (collision avoidance → Z={z_raised:.1f} mm)",
                target_x=current_x,
                target_y=current_y,
                target_z=z_raised,
            ),
            MotionStep(
                description=f"[{label}] Move XY to alignment position"
                            f"  (target X={target_x:.3f}  Y={target_y:.3f} mm)",
                target_x=target_x,
                target_y=target_y,
                target_z=z_raised,           # XY at raised Z
            ),
            MotionStep(
                description=f"[{label}] Lower Z to approach height"
                            f"  (Z={APPROACH_Z:.1f} mm — SFC opening at {SFC_Z:.1f} mm)",
                target_x=target_x,
                target_y=target_y,
                target_z=APPROACH_Z,
            ),
        ]

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _require_loaded(self) -> None:
        if self._reference is None:
            raise ValueError("No reference pixel loaded.  Call load_spots() first.")
        if not self._spots:
            raise ValueError("No spots loaded.  Call load_spots() first.")

    def _compute(self, spot: dict) -> AlignmentResult:
        """Core alignment math for one spot dict {"label", "x", "y"}."""
        x_ref = self._reference["x"]
        y_ref = self._reference["y"]
        x_spot = spot["x"]
        y_spot = spot["y"]

        dx_pixels = x_spot - x_ref
        dy_pixels = y_spot - y_ref

        sign_x = -1.0 if self.invert_x else 1.0
        sign_y = -1.0 if self.invert_y else 1.0

        # Axis swap: image X (horizontal) → stage Y, image Y (vertical) → stage X
        real_offset_x = sign_x * dy_pixels * self.pixel_scale
        real_offset_y = sign_y * dx_pixels * self.pixel_scale

        # Absolute stage target: bring spot under SFC opening
        #   TARGET_Y = REF_STAGE_Y + (ref_xPixel - spot_xPixel) * scale - SFC_Y
        #   TARGET_X = REF_STAGE_X - (ref_yPixel - spot_yPixel) * scale - SFC_X
        target_x = REF_STAGE_X - SFC_X - real_offset_x
        target_y = REF_STAGE_Y - SFC_Y - real_offset_y

        # Delta from REF_STAGE (used for logging and stage_target())
        stage_move_x = target_x - REF_STAGE_X
        stage_move_y = target_y - REF_STAGE_Y

        return AlignmentResult(
            label=spot["label"],
            pixel_pos=(x_spot, y_spot),
            pixel_offset=(dx_pixels, dy_pixels),
            real_offset_mm=(round(real_offset_x, 3), round(real_offset_y, 3)),
            stage_move_mm=(round(stage_move_x, 3), round(stage_move_y, 3)),
        )
