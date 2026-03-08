# excel_export.py

from openpyxl import Workbook


def export_results_to_excel(path, result):

    wb = Workbook()
    ws = wb.active

    ws.title="Summary"

    ws.append(["Detected",len(result["all_spots"])])
    ws.append(["Accepted",len(result["accepted_spots"])])
    ws.append(["Rejected",len(result["rejected_spots"])])

    ws2 = wb.create_sheet("Spots")

    ws2.append([
        "Label",
        "Status",
        "Area",
        "Circularity",
        "Solidity"
    ])

    for s in result["all_spots"]:

        status = "Rejected" if s.get("is_bad") else "Accepted"

        ws2.append([
            s.get("label"),
            status,
            s["area"],
            s["circularity"],
            s["solidity"]
        ])

    wb.save(path)