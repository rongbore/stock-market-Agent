"""Large-input and boundary regressions for conservative financial period hints."""

import unittest

from scripts.financial_table_period_hints import table_period_hints


def make_cell(text, row, column):
    return {
        "page": 1,
        "table_index": 0,
        "row_index": row,
        "column_index": column,
        "text": text,
        "bbox": [10, row * 20, 90, row * 20 + 10],
    }


class PeriodHintsLargeInputTests(unittest.TestCase):
    def test_twenty_thousand_cells_with_many_preceding_headers(self):
        # 200 distinct header rows and 19,800 numeric cells exercise the
        # repeated-header lookup without imposing a flaky wall-clock limit.
        headers = [make_cell("本报告期", row, 0) for row in range(200)]
        values = [
            make_cell("1", row, col)
            for row in range(200, 400)
            for col in range(99)
        ]
        result = table_period_hints(headers + values)
        self.assertEqual(len(result["candidates"]), 19800)
        self.assertTrue(all(
            item["period_hint_unverified"] == "current_quarter"
            and item["reason"] == "unique_header_rectangle"
            and not item["column_ownership_verified"]
            for item in result["candidates"]
        ))
        self.assertFalse(result["financial_meaning_verified"])
        self.assertFalse(result["column_ownership_verified"])

    def test_above_twenty_thousand_cells_rejected(self):
        cells = [make_cell("1", row, col)
                 for row in range(201) for col in range(100)]
        with self.assertRaises(ValueError):
            table_period_hints(cells)


if __name__ == "__main__":
    unittest.main()
