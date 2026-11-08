"""Conservative period hints from extracted table cells, never verified attribution."""
import re

from scripts.financial_pdf_geometry import inspect_spans

HEADERS = {"本报告期": "current_quarter", "年初至报告期末": "year_to_date",
           "本报告期末": "period_end", "上年度末": "previous_year_end"}
NUMBER = re.compile(r"-?(?:[0-9]+|[0-9]{1,3}(?:,[0-9]{3})+)(?:\.[0-9]+)?")


def table_period_hints(cells):
    """Use the nearest preceding header row and horizontal cell containment."""
    if not isinstance(cells, list) or len(cells) > 20000:
        raise ValueError("invalid cell collection")
    usable = []
    locations = set()
    for cell in cells:
        if not isinstance(cell, dict):
            raise ValueError("invalid cell")
        for key in ("page", "table_index", "row_index", "column_index"):
            if type(cell.get(key)) is not int or cell[key] < (1 if key == "page" else 0):
                raise ValueError("invalid cell position")
        location = tuple(cell[k] for k in ("page", "table_index", "row_index", "column_index"))
        if location in locations:
            raise ValueError("duplicate cell position")
        locations.add(location)
        if cell.get("text") is None and cell.get("bbox") is None:
            continue
        inspect_spans([cell])
        usable.append({**cell, "text": "".join(cell["text"].split())})
    groups = {}
    for cell in usable:
        groups.setdefault((cell["page"], cell["table_index"]), []).append(cell)
    candidates = []
    for group in groups.values():
        headers = [c for c in group if c["text"] in HEADERS]
        for cell in group:
            if not NUMBER.fullmatch(cell["text"]):
                continue
            preceding = [h for h in headers if h["row_index"] < cell["row_index"]
                         and h["bbox"][3] <= cell["bbox"][1]]
            row = max((h["row_index"] for h in preceding), default=None)
            center = (cell["bbox"][0] + cell["bbox"][2]) / 2
            matches = [h for h in preceding if h["row_index"] == row
                       and h["bbox"][0] < center < h["bbox"][2]]
            header = matches[0] if len(matches) == 1 else None
            candidates.append({"cell": cell, "header_cell": header,
                               "period_hint_unverified": HEADERS[header["text"]] if header else None,
                               "reason": "unique_header_rectangle" if header else "missing_or_ambiguous_header",
                               "column_ownership_verified": False})
    return {"candidates": candidates, "financial_meaning_verified": False,
            "column_ownership_verified": False}
