"""
Side-by-side comparison: GPT_Merge (v1) vs GPT_Merge_v2 vs GPT_Merge_v3.

Runs all pipelines on test images in doc/ and prints comparison tables.
Saves output images to doc/<name>_v1/, doc/<name>_v2/, doc/<name>_v3/.
"""

import sys
import os
from pathlib import Path

os.environ["PYTHONIOENCODING"] = "utf-8"

PROJECT_ROOT = Path(__file__).parent
sys.path.insert(0, str(PROJECT_ROOT))

from device_drivers import GPT_Merge as v1
from device_drivers import GPT_Merge_v2 as v2
from device_drivers import GPT_Merge_v3 as v3

ALL_IMAGES = [
    ("IMG_0747", PROJECT_ROOT / "doc" / "IMG_0747.png"),
    ("plate",    PROJECT_ROOT / "doc" / "plate.png"),
]

PIPELINES = [
    ("v1", "v1 (original GPT_Merge)", v1),
    ("v2", "v2 (adaptive GPT_Merge_v2)", v2),
    ("v3", "v3 (ensemble GPT_Merge_v3)", v3),
]


def run_pipeline(label, module, image_path, out_dir):
    print(f"\n  {label}")
    print(f"  {'-'*50}")

    result = module.analyze_plate_and_spots(str(image_path), str(out_dir))

    if not result["plate_detected"]:
        print(f"  ERROR: {result['error']}")
        return result

    all_spots = result["all_spots"]
    accepted = result["accepted_spots"]
    rejected = result["rejected_spots"]
    bbox = result["plate_bbox"]

    print(f"  Plate bbox : x={bbox[0]}, y={bbox[1]}, w={bbox[2]}, h={bbox[3]}")
    print(f"  Total spots: {len(all_spots)}")
    print(f"  Accepted   : {len(accepted)}")
    print(f"  Rejected   : {len(rejected)}")

    if all_spots:
        areas = [s.get("area", s["radius"] ** 2 * 3.14159) for s in all_spots]
        radii = [s["radius"] for s in all_spots]
        circs = [s.get("circularity", 0) for s in all_spots]
        sources = [s.get("_source", "contour") for s in all_spots]
        print(f"  Area  range: {min(areas):.0f} - {max(areas):.0f} px")
        print(f"  Radius range: {min(radii):.1f} - {max(radii):.1f} px")
        if any(c > 0 for c in circs):
            print(f"  Circ  range: {min(circs):.3f} - {max(circs):.3f}")
        # Show source breakdown for v3
        if any(src != "contour" for src in sources):
            from collections import Counter
            src_counts = Counter(sources)
            parts = [f"{k}={v}" for k, v in sorted(src_counts.items())]
            print(f"  Sources    : {', '.join(parts)}")

    if accepted:
        print(f"  Accepted: {', '.join(s['label'] for s in accepted)}")
    if rejected:
        # Show rejection reasons if available (v3)
        parts = []
        for s in rejected:
            reason = s.get("_reject_reason", "defect")
            parts.append(f"{s['label']}({reason})")
        print(f"  Rejected: {', '.join(parts)}")

    return result


def count(r, key):
    return len(r.get(key, [])) if r.get("plate_detected") else "N/A"


def delta(a, b):
    if isinstance(a, int) and isinstance(b, int):
        d = b - a
        return f"+{d}" if d > 0 else str(d)
    return "-"


def main():
    for name, img_path in ALL_IMAGES:
        print(f"\n{'='*70}")
        print(f"  IMAGE: {name}  ({img_path.name})")
        print(f"  Exists: {img_path.exists()}")
        print(f"{'='*70}")

        if not img_path.exists():
            print(f"  SKIPPED: file not found")
            continue

        results = {}
        for tag, label, module in PIPELINES:
            out_dir = str(PROJECT_ROOT / "doc" / f"{name}_{tag}")
            results[tag] = run_pipeline(label, module, img_path, out_dir)

        # Summary table
        print(f"\n  {'Metric':<25}", end="")
        for tag, _, _ in PIPELINES:
            print(f" {tag:>8}", end="")
        print(f" {'v1->v3':>8}")

        print(f"  {'-'*25}", end="")
        for _ in PIPELINES:
            print(f" {'-'*8}", end="")
        print(f" {'-'*8}")

        for metric_key, metric_label in [
            ("all_spots", "Total detected"),
            ("accepted_spots", "Accepted"),
            ("rejected_spots", "Rejected"),
        ]:
            counts = {tag: count(results[tag], metric_key) for tag, _, _ in PIPELINES}
            print(f"  {metric_label:<25}", end="")
            for tag, _, _ in PIPELINES:
                print(f" {str(counts[tag]):>8}", end="")
            print(f" {delta(counts['v1'], counts['v3']):>8}")

        out_dirs = [f"doc/{name}_{tag}/" for tag, _, _ in PIPELINES]
        print(f"\n  Output: {' | '.join(out_dirs)}")


if __name__ == "__main__":
    main()
