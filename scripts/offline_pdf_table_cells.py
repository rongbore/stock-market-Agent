"""Extract bounded, unverified table cells without flattening placeholder signs."""
import math
from pathlib import Path

from scripts.disclosure_pdf_fingerprint import fingerprint


def extract_table_cells(path, symbol, announcement_date, page_numbers, opener=None):
    """Preserve row/column positions and cell rectangles; infer no financial meaning."""
    if (not isinstance(page_numbers, list) or not 1 <= len(page_numbers) <= 20
            or any(type(n) is not int or not 1 <= n <= 10000 for n in page_numbers)
            or len(set(page_numbers)) != len(page_numbers)):
        raise ValueError("invalid requested table pages")
    path = Path(path)
    before = fingerprint(path, symbol, announcement_date)
    if opener is None:
        import pdfplumber
        opener = pdfplumber.open
    cells = []
    with opener(path) as pdf:
        if any(n > len(pdf.pages) for n in page_numbers):
            raise ValueError("table page out of range")
        for number in page_numbers:
            tables = pdf.pages[number - 1].find_tables()
            if len(tables) > 20:
                raise ValueError("too many tables")
            for table_index, table in enumerate(tables):
                rows = table.extract()
                if len(rows) > 500 or len(rows) != len(table.rows):
                    raise ValueError("invalid table row count")
                for row_index, row in enumerate(rows):
                    boxes = table.rows[row_index].cells
                    if len(row) > 100 or len(row) != len(boxes):
                        raise ValueError("invalid table column count")
                    for column_index, (text, box) in enumerate(zip(row, boxes)):
                        if text is not None and (not isinstance(text, str) or len(text) > 2000):
                            raise ValueError("invalid cell text")
                        if box is not None:
                            if (len(box) != 4 or any(not isinstance(v, (int, float))
                                    or not math.isfinite(v) for v in box)
                                    or not 0 <= box[0] < box[2]
                                    or not 0 <= box[1] < box[3]):
                                raise ValueError("invalid cell rectangle")
                        cells.append({"page": number, "table_index": table_index,
                                      "row_index": row_index, "column_index": column_index,
                                      "text": text, "bbox": list(box) if box is not None else None})
                        if len(cells) > 20000:
                            raise ValueError("too many table cells")
    after = fingerprint(path, symbol, announcement_date)
    if before["file_sha256"] != after["file_sha256"]:
        raise ValueError("PDF changed during table extraction")
    return {"file_sha256": before["file_sha256"], "cells": cells,
            "status": "PENDING_MANUAL_VERIFICATION", "official_origin_verified": False,
            "column_ownership_verified": False, "financial_meaning_verified": False}
