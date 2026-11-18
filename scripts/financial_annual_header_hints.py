"""Explicit year/restatement hints; never relative-period or verified attribution."""
from bisect import bisect_left
import re

from scripts.financial_table_period_hints import NUMBER, table_period_hints

YEAR = re.compile(r"((?:19|20)[0-9]{2})年(末)?")
RESTATEMENT = {"调整前": "before_adjustment", "调整后": "after_adjustment"}


def _partition_child(header, children, row_numbers, target):
    """Require an explicit two-cell tiling, never extrapolate header widths."""
    if len(children) != 2 or {c["text"] for c in children} != set(RESTATEMENT):
        return None
    siblings = sorted([n for n in row_numbers
                       if header["bbox"][0] <= n["bbox"][0] < n["bbox"][2] <= header["bbox"][2]],
                      key=lambda n: n["bbox"][0])
    if len(siblings) != 2:
        return None
    left, right = siblings
    if (abs(left["bbox"][0] - header["bbox"][0]) > 1e-6
            or abs(left["bbox"][2] - right["bbox"][0]) > 1e-6
            or abs(right["bbox"][2] - header["bbox"][2]) > 1e-6
            or left["bbox"][1] != right["bbox"][1] or left["bbox"][3] != right["bbox"][3]):
        return None
    if children[0]["bbox"][1] != children[1]["bbox"][1] or children[0]["bbox"][3] != children[1]["bbox"][3]:
        return None
    labels = []
    for number in siblings:
        matches = [h for h in children
                   if number["bbox"][0] <= h["bbox"][0] < h["bbox"][2] <= number["bbox"][2]
                   and header["bbox"][3] <= h["bbox"][1] and h["bbox"][3] <= number["bbox"][1]]
        if len(matches) != 1:
            return None
        labels.append(matches[0])
    return (labels[siblings.index(target)], siblings) if target in siblings else None


def annual_header_hints(cells):
    """Use latest year block, full horizontal containment and explicit subheaders."""
    validated = table_period_hints(cells)  # Existing bounded position/geometry checks.
    if any(c["row_index"] >= 500 or c["column_index"] >= 100 or c["table_index"] >= 20 for c in cells):
        raise ValueError("annual table position outside extraction bounds")
    groups = {}
    for cell in cells:
        if cell.get("text") is not None and cell.get("bbox") is not None:
            normalized = {**cell, "text": "".join(cell["text"].split())}
            groups.setdefault((cell["page"], cell["table_index"]), []).append(normalized)
    numbers = {}
    row_numbers = {}
    for candidate in validated["candidates"]:
        cell = candidate["cell"]
        numbers.setdefault((cell["page"], cell["table_index"]), []).append(cell)
        row_numbers.setdefault((cell["page"], cell["table_index"], cell["row_index"]), []).append(cell)
    result = []
    for key, group in groups.items():
        by_row = {}
        for cell in group:
            by_row.setdefault(cell["row_index"], []).append(cell)
        year_rows = sorted(row for row, items in by_row.items() if any(YEAR.fullmatch(c["text"]) for c in items))
        # Pure text rows with unknown content are section barriers. Never carry
        # a prior annual header through quarterly or other unrecognized headers.
        barriers = sorted(row for row, items in by_row.items()
                          if any(c["text"] for c in items)
                          and not any(NUMBER.fullmatch(c["text"]) for c in items)
                          and not any(YEAR.fullmatch(c["text"]) for c in items)
                          and any(c["text"] and c["text"] not in RESTATEMENT and c["text"] != "项目" for c in items))
        barrier_boxes = {row: (min(c["bbox"][0] for c in by_row[row] if c["text"]),
                               max(c["bbox"][2] for c in by_row[row] if c["text"])) for row in barriers}
        sub_rows = sorted(row for row, items in by_row.items()
                          if any(c["text"] in RESTATEMENT for c in items))
        for cell in numbers.get(key, []):
            hint = {"cell": cell, "year_hint_unverified": None, "basis_hint_unverified": None,
                    "restatement_hint_unverified": None, "year_header_cell": None,
                    "restatement_header_cell": None, "partition_cells_unverified": [], "reason": "missing_or_ambiguous_year_header",
                    "column_ownership_verified": False, "financial_meaning_verified": False}
            index = bisect_left(year_rows, cell["row_index"]) - 1
            if index < 0:
                result.append(hint)
                continue
            row = year_rows[index]
            intervening = barriers[bisect_left(barriers, row + 1):bisect_left(barriers, cell["row_index"])]
            if any(barrier_boxes[b][0] < cell["bbox"][2] and barrier_boxes[b][1] > cell["bbox"][0]
                   for b in intervening):
                result.append(hint)
                continue
            headers = [h for h in by_row[row] if YEAR.fullmatch(h["text"])
                       and h["bbox"][3] <= cell["bbox"][1]
                       and h["bbox"][0] <= cell["bbox"][0] < cell["bbox"][2] <= h["bbox"][2]]
            if len(headers) != 1:
                result.append(hint)
                continue
            header = headers[0]
            # Only explicit child rectangles fully inside this year rectangle
            # may disambiguate restatement basis. Do not infer a default basis.
            sub_index = bisect_left(sub_rows, cell["row_index"]) - 1
            children = []
            if sub_index >= 0 and sub_rows[sub_index] >= row:
                children = [h for h in by_row[sub_rows[sub_index]] if h["text"] in RESTATEMENT
                            and h["bbox"][0] < header["bbox"][2] and h["bbox"][2] > header["bbox"][0]]
            child = None
            partition_used = False
            if children:
                matches = [h for h in children
                           if header["bbox"][0] <= h["bbox"][0] < h["bbox"][2] <= header["bbox"][2]
                           and header["bbox"][3] <= h["bbox"][1] and h["bbox"][3] <= cell["bbox"][1]
                           and h["bbox"][0] <= cell["bbox"][0] < cell["bbox"][2] <= h["bbox"][2]]
                if len(matches) == 1:
                    child = matches[0]
                else:
                    partition = _partition_child(header, children, row_numbers[(key[0], key[1], cell["row_index"])], cell)
                    if partition is None:
                        hint["reason"] = "missing_or_ambiguous_restatement_header"
                        result.append(hint)
                        continue
                    child, hint["partition_cells_unverified"] = partition
                    partition_used = True
            match = YEAR.fullmatch(header["text"])
            hint.update(year_hint_unverified=int(match[1]),
                        basis_hint_unverified="year_end" if match[2] else "annual",
                        restatement_hint_unverified=RESTATEMENT[child["text"]] if child else None,
                        year_header_cell=header, restatement_header_cell=child,
                        reason="explicit_restatement_row_partition_unverified" if partition_used else "explicit_year_header_chain_unverified")
            result.append(hint)
    return {"schema_version": "0.1", "candidates": result,
            "hint_count": sum(c["year_hint_unverified"] is not None for c in result),
            "financial_meaning_verified": False, "column_ownership_verified": False,
            "limitations": ["Explicit year labels are not proof of period or consolidation scope.",
                            "Absent restatement label means unknown, not unadjusted.",
                            "Hints do not clear relative-period or manual-review blockers."]}
