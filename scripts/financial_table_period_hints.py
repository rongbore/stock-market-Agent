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
        # Index headers by row; each tree node stores the minimum bottom y.
        # Query rightmost eligible row in O(log H), without scanning every header.
        headers = [c for c in group if c["text"] in HEADERS]
        rows = sorted({h["row_index"] for h in headers})
        by_row = {row: [] for row in rows}
        for header in headers:
            by_row[header["row_index"]].append(header)
        size = 1
        while size < len(rows):
            size *= 2
        tree = [float("inf")] * (2 * size)
        for index, row in enumerate(rows):
            tree[size + index] = min(h["bbox"][3] for h in by_row[row])
        for index in range(size - 1, 0, -1):
            tree[index] = min(tree[2 * index], tree[2 * index + 1])

        def latest_row(limit, top):
            # Search only header rows strictly earlier than the numeric row.
            def visit(node, left, right):
                if left >= limit or tree[node] > top:
                    return None
                if right - left == 1:
                    return rows[left] if left < len(rows) else None
                mid = (left + right) // 2
                return (visit(node * 2 + 1, mid, right)
                        or visit(node * 2, left, mid))
            return visit(1, 0, size)

        for cell in group:
            if not NUMBER.fullmatch(cell["text"]):
                continue
            from bisect import bisect_left
            row = latest_row(bisect_left(rows, cell["row_index"]),
                             cell["bbox"][1])
            center = (cell["bbox"][0] + cell["bbox"][2]) / 2
            matches = [h for h in by_row.get(row, ())
                       if h["bbox"][3] <= cell["bbox"][1]
                       and h["bbox"][0] < center < h["bbox"][2]]
            header = matches[0] if len(matches) == 1 else None
            candidates.append({"cell": cell, "header_cell": header,
                               "period_hint_unverified": HEADERS[header["text"]] if header else None,
                               "reason": "unique_header_rectangle" if header else "missing_or_ambiguous_header",
                               "column_ownership_verified": False})
    return {"candidates": candidates, "financial_meaning_verified": False,
            "column_ownership_verified": False}
