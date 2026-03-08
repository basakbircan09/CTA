# pipeline.py
"""End-to-end spot analysis pipeline.

Public API
----------
run_spot_analysis(image_path, output_dir, export_excel) -> dict

Returned dict always contains:
    all_spots              list[dict]   – every accepted candidate spot (with labels)
    accepted_spots         list[dict]   – spots with no detected defects
    rejected_spots         list[dict]   – spots flagged as defective
    rejected_candidates    list[dict]   – contours filtered out during detection
    overlay_image          np.ndarray   – BGR accept/reject colour overlay
    rejected_candidates_overlay  np.ndarray  – BGR yellow overlay of detection rejects
    accepted_labels        list[str]    – labels of good spots  (e.g. ["A1", "A2"])
    rejected_labels        list[str]    – labels of bad spots   (e.g. ["B3"])
    missing_spots          list[str]    – expected grid labels that are absent
    per_spot_metrics       dict         – {label: metrics_dict} for every accepted spot
    excel_path             str | None   – path to saved .xlsx, or None
    error                  str | None   – non-fatal error description, or None

Debug images saved to output_dir (when provided)
-------------------------------------------------
    01_original.png
    02_gray_raw.png
    03_bg.png
    04_gray_norm.png
    05_blur.png
    06_thresh_bw.png
    07_opened.png
    08_closed.png
    09_rejected_candidates_overlay.png
    10_accept_reject_overlay.png
"""

import cv2
from pathlib import Path

from .detection import detect_spots, sort_and_label, find_missing_spots
from .inspection import inspect_spot_defects
from .visualization import draw_accept_reject_overlay, draw_rejected_candidates_overlay
from .excel_export import export_results_to_excel


def _save(out: Path, name: str, img) -> None:
    """Write a debug image to disk if out is not None."""
    if out is None or img is None:
        return
    out.mkdir(parents=True, exist_ok=True)
    cv2.imwrite(str(out / name), img)


def run_spot_analysis(
    image_path: str,
    output_dir: str = None,
    export_excel: bool = True,
) -> dict:
    """Run the full spot analysis pipeline on a plate image.

    Args:
        image_path:   Path to the plate image (PNG / JPG / BMP).
        output_dir:   Directory to save debug images and spot_results.xlsx.
                      Pass None to skip saving.
        export_excel: Whether to write an Excel report (only when output_dir
                      is given).

    Returns:
        Standardised result dict (see module docstring for keys).

    Raises:
        ValueError: If the image cannot be loaded.
    """
    out = Path(output_dir) if output_dir else None

    # ------------------------------------------------------------------
    # Load
    # ------------------------------------------------------------------
    img = cv2.imread(str(image_path))
    if img is None:
        raise ValueError(f"Cannot load image: {image_path}")

    _save(out, "01_original.png", img)

    # ------------------------------------------------------------------
    # Detection
    # ------------------------------------------------------------------
    det_dbg: dict = {}
    spots, rejected_candidates, _ = detect_spots(img, debug=det_dbg)

    _save(out, "02_gray_raw.png",  det_dbg.get("gray_raw"))
    _save(out, "03_bg.png",        det_dbg.get("bg"))
    _save(out, "04_gray_norm.png", det_dbg.get("gray_norm"))
    _save(out, "05_blur.png",      det_dbg.get("blur"))
    _save(out, "06_thresh_bw.png", det_dbg.get("thresh_bw"))
    _save(out, "07_opened.png",    det_dbg.get("opened"))
    _save(out, "08_closed.png",    det_dbg.get("closed"))

    gray_norm = det_dbg["gray_norm"]

    # ------------------------------------------------------------------
    # Grid labelling  (done before inspection so labels exist in metrics)
    # ------------------------------------------------------------------
    sort_and_label(spots)

    # ------------------------------------------------------------------
    # Defect inspection
    # ------------------------------------------------------------------
    accepted: list = []
    rejected: list = []
    per_spot_metrics: dict = {}

    for s in spots:
        is_bad, metrics = inspect_spot_defects(gray_norm, s)
        s["is_bad"] = is_bad
        s["metrics"] = metrics
        if "label" in s:
            per_spot_metrics[s["label"]] = metrics
        if is_bad:
            rejected.append(s)
        else:
            accepted.append(s)

    # ------------------------------------------------------------------
    # Visualisation
    # ------------------------------------------------------------------
    cand_overlay = draw_rejected_candidates_overlay(img, rejected_candidates)
    overlay      = draw_accept_reject_overlay(img, spots)

    _save(out, "09_rejected_candidates_overlay.png", cand_overlay)
    _save(out, "10_accept_reject_overlay.png",       overlay)

    # ------------------------------------------------------------------
    # Grid gap detection
    # ------------------------------------------------------------------
    missing_spots = find_missing_spots(spots)

    # ------------------------------------------------------------------
    # Build result dict
    # ------------------------------------------------------------------
    accepted_labels = [s.get("label", "?") for s in accepted]
    rejected_labels = [s.get("label", "?") for s in rejected]

    result: dict = {
        "all_spots":                    spots,
        "accepted_spots":               accepted,
        "rejected_spots":               rejected,
        "rejected_candidates":          rejected_candidates,
        "overlay_image":                overlay,
        "rejected_candidates_overlay":  cand_overlay,
        "accepted_labels":              accepted_labels,
        "rejected_labels":              rejected_labels,
        "missing_spots":                missing_spots,
        "per_spot_metrics":             per_spot_metrics,
        "excel_path":                   None,
        "error":                        None,
    }

    # ------------------------------------------------------------------
    # Excel export
    # ------------------------------------------------------------------
    if out and export_excel:
        out.mkdir(parents=True, exist_ok=True)
        excel_path = str(out / "spot_results.xlsx")
        try:
            export_results_to_excel(excel_path, result)
            result["excel_path"] = excel_path
        except Exception as exc:
            result["error"] = f"Excel export failed: {exc}"

    return result
