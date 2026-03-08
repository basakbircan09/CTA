# pipeline.py
"""End-to-end spot analysis pipeline.

Public API
----------
run_spot_analysis(image_path, output_dir, export_excel) -> dict

Returned dict always contains:
    all_spots           list[dict]   – every accepted candidate spot
    accepted_spots      list[dict]   – spots with no detected defects
    rejected_spots      list[dict]   – spots flagged as defective
    rejected_candidates list[dict]   – contours filtered out during detection
    overlay_image       np.ndarray   – BGR image with colour-coded overlays
    accepted_labels     list[str]    – labels of good spots  (e.g. ["A1", "A2"])
    rejected_labels     list[str]    – labels of bad spots   (e.g. ["B3"])
    missing_spots       list[str]    – expected grid labels that are absent
    excel_path          str | None   – path to saved .xlsx, or None
    error               str | None   – non-fatal error description, or None
"""

import cv2
from pathlib import Path

from .detection import detect_spots, sort_and_label, find_missing_spots
from .inspection import inspect_spot_defects
from .visualization import draw_accept_reject_overlay
from .excel_export import export_results_to_excel


def run_spot_analysis(
    image_path: str,
    output_dir: str = None,
    export_excel: bool = True,
) -> dict:
    """Run the full spot analysis pipeline on a plate image.

    Args:
        image_path:   Path to the plate image (PNG / JPG / BMP).
        output_dir:   Directory to save overlay.png and spot_results.xlsx.
                      Pass None to skip saving.
        export_excel: Whether to write an Excel report (only when output_dir
                      is given).

    Returns:
        Standardised result dict (see module docstring for keys).

    Raises:
        ValueError: If the image cannot be loaded.
    """
    # ------------------------------------------------------------------
    # Load
    # ------------------------------------------------------------------
    img = cv2.imread(str(image_path))
    if img is None:
        raise ValueError(f"Cannot load image: {image_path}")

    # ------------------------------------------------------------------
    # Detection
    # ------------------------------------------------------------------
    spots, rejected_candidates, debug = detect_spots(img)
    gray_norm = debug["gray_norm"]

    # ------------------------------------------------------------------
    # Defect inspection
    # ------------------------------------------------------------------
    accepted: list = []
    rejected: list = []

    for s in spots:
        is_bad, metrics = inspect_spot_defects(gray_norm, s)
        s["is_bad"] = is_bad
        s["metrics"] = metrics
        if is_bad:
            rejected.append(s)
        else:
            accepted.append(s)

    # ------------------------------------------------------------------
    # Grid labelling and gap detection
    # ------------------------------------------------------------------
    sort_and_label(spots)                    # mutates spots in-place
    missing_spots = find_missing_spots(spots)

    # ------------------------------------------------------------------
    # Visualisation
    # ------------------------------------------------------------------
    overlay = draw_accept_reject_overlay(img, spots)

    # ------------------------------------------------------------------
    # Build result dict
    # ------------------------------------------------------------------
    accepted_labels = [s.get("label", "?") for s in accepted]
    rejected_labels = [s.get("label", "?") for s in rejected]

    result: dict = {
        "all_spots": spots,
        "accepted_spots": accepted,
        "rejected_spots": rejected,
        "rejected_candidates": rejected_candidates,
        "overlay_image": overlay,
        "accepted_labels": accepted_labels,
        "rejected_labels": rejected_labels,
        "missing_spots": missing_spots,
        "excel_path": None,
        "error": None,
    }

    # ------------------------------------------------------------------
    # Save artefacts
    # ------------------------------------------------------------------
    if output_dir:
        out = Path(output_dir)
        out.mkdir(parents=True, exist_ok=True)

        cv2.imwrite(str(out / "overlay.png"), overlay)

        if export_excel:
            excel_path = str(out / "spot_results.xlsx")
            try:
                export_results_to_excel(excel_path, result)
                result["excel_path"] = excel_path
            except Exception as exc:
                result["error"] = f"Excel export failed: {exc}"

    return result
