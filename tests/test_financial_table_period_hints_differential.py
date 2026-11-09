"""Differential contract tests before optimizing financial period header lookup."""
import random
import unittest

from scripts.financial_table_period_hints import HEADERS, NUMBER, table_period_hints


def reference(cells):
    """Intentionally simple independent O(cells * headers) baseline."""
    groups = {}
    for cell in cells:
        cleaned = {**cell, "text": "".join(cell["text"].split())}
        groups.setdefault((cell["page"], cell["table_index"]), []).append(cleaned)
    candidates = []
    for group in groups.values():
        headers = [item for item in group if item["text"] in HEADERS]
        for item in group:
            if not NUMBER.fullmatch(item["text"]):
                continue
            eligible = [h for h in headers
                        if h["row_index"] < item["row_index"]
                        and h["bbox"][3] <= item["bbox"][1]]
            latest = max((h["row_index"] for h in eligible), default=None)
            midpoint = (item["bbox"][0] + item["bbox"][2]) / 2
            matching = [h for h in eligible
                        if h["row_index"] == latest
                        and h["bbox"][0] < midpoint < h["bbox"][2]]
            header = matching[0] if len(matching) == 1 else None
            candidates.append({
                "cell": item, "header_cell": header,
                "period_hint_unverified": HEADERS[header["text"]] if header else None,
                "reason": "unique_header_rectangle" if header else "missing_or_ambiguous_header",
                "column_ownership_verified": False,
            })
    return {"candidates": candidates, "financial_meaning_verified": False,
            "column_ownership_verified": False}


class PeriodHintDifferentialTests(unittest.TestCase):
    def test_randomized_layouts_match_reference(self):
        rng = random.Random(20261109)
        texts = list(HEADERS) + ["1", "-12.50", "1,000.00", "—", "说明"]
        for trial in range(300):
            cells = []
            for column in range(rng.randrange(1, 31)):
                page = rng.randrange(1, 4)
                table = rng.randrange(3)
                row = rng.randrange(15)
                # Unique position, including multiple cells on a single row.
                index = (trial * 100 + column)
                x0 = rng.randrange(0, 150)
                x1 = x0 + rng.randrange(1, 100)
                y0 = rng.randrange(0, 250)
                y1 = y0 + rng.randrange(1, 30)
                cells.append({
                    "page": page, "table_index": table,
                    "row_index": row, "column_index": index,
                    "text": rng.choice(texts),
                    "bbox": [x0, y0, x1, y1],
                })
            self.assertEqual(table_period_hints(cells), reference(cells),
                             "layout trial %s" % trial)

    def test_latest_eligible_row_blocks_older_matching_header(self):
        cells = [
            {"page": 1, "table_index": 0, "row_index": 0,
             "column_index": 0, "text": "本报告期", "bbox": [0, 0, 100, 10]},
            {"page": 1, "table_index": 0, "row_index": 1,
             "column_index": 0, "text": "上年度末", "bbox": [120, 20, 200, 30]},
            {"page": 1, "table_index": 0, "row_index": 2,
             "column_index": 0, "text": "12", "bbox": [10, 40, 20, 50]},
        ]
        result = table_period_hints(cells)
        self.assertIsNone(result["candidates"][0]["period_hint_unverified"])
        self.assertEqual(result, reference(cells))


if __name__ == "__main__":
    unittest.main()
