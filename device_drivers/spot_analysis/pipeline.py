# pipeline.py

import cv2
from pathlib import Path

from .detection import detect_spots
from .inspection import inspect_spot_defects
from .visualization import draw_accept_reject_overlay
from .excel_export import export_results_to_excel


def run_spot_analysis(image_path, output_dir=None, export_excel=True):

    img = cv2.imread(image_path)

    spots, rejected_candidates, debug = detect_spots(img)

    accepted=[]
    rejected=[]

    gray = debug["gray_norm"]

    for s in spots:

        bad,metrics = inspect_spot_defects(gray,s)

        s["is_bad"]=bad
        s["metrics"]=metrics

        if bad:
            rejected.append(s)
        else:
            accepted.append(s)

    overlay = draw_accept_reject_overlay(img, spots)

    result={
        "all_spots":spots,
        "accepted_spots":accepted,
        "rejected_spots":rejected,
        "rejected_candidates":rejected_candidates,
        "overlay_image":overlay,
    }

    if output_dir:

        Path(output_dir).mkdir(exist_ok=True)

        cv2.imwrite(str(Path(output_dir)/"overlay.png"),overlay)

        if export_excel:

            export_results_to_excel(
                str(Path(output_dir)/"spot_results.xlsx"),
                result
            )

    return result