# excel_export.py

from openpyxl import Workbook


def export_results_to_excel(path: str, result: dict) -> None:
    """Write spot analysis results to an .xlsx workbook.

    Sheets:
        Summary  – total / accepted / rejected counts plus label lists
        Spots    – per-spot table with label, status, and shape metrics
    """
    wb = Workbook()
    ws = wb.active
    ws.title = "Summary"

    ws.append(["Detected", len(result["all_spots"])])
    ws.append(["Accepted", len(result["accepted_spots"])])
    ws.append(["Rejected", len(result["rejected_spots"])])

    accepted_labels = result.get("accepted_labels", [])
    if accepted_labels:
        ws.append(["Accepted Labels", ", ".join(accepted_labels)])

    rejected_labels = result.get("rejected_labels", [])
    if rejected_labels:
        ws.append(["Rejected Labels", ", ".join(rejected_labels)])

    missing = result.get("missing_spots", [])
    if missing:
        ws.append(["Missing Spots", ", ".join(missing)])

    ws2 = wb.create_sheet("Spots")
    ws2.append(["Label", "Status", "Area", "Circularity", "Solidity"])

    for s in result["all_spots"]:
        status = "Rejected" if s.get("is_bad") else "Accepted"
        ws2.append([
            s.get("label", ""),
            status,
            round(float(s["area"]), 1),
            round(float(s["circularity"]), 4),
            round(float(s["solidity"]), 4),
        ])

    wb.save(path)