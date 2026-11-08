import unittest
from types import SimpleNamespace
from unittest.mock import patch, MagicMock

from scripts.offline_pdf_table_cells import extract_table_cells


class TableCellTests(unittest.TestCase):
    def extract(self, rows, boxes):
        table = SimpleNamespace(extract=lambda: rows,
                                rows=[SimpleNamespace(cells=row) for row in boxes])
        pdf = SimpleNamespace(pages=[SimpleNamespace(find_tables=lambda: [table])])
        context = MagicMock()
        context.__enter__.return_value = pdf
        with patch("scripts.offline_pdf_table_cells.fingerprint",
                   return_value={"file_sha256": "a" * 64}):
            return extract_table_cells("x.pdf", "000776.SZ", "2026-10-30", [1],
                                       opener=lambda _: context)

    def test_preserves_negative_value_placeholder_and_merged_slot(self):
        result = self.extract([["-", None, "-8,137,823,726.59"]],
                              [[(0, 0, 10, 10), None, (20, 0, 40, 10)]])
        self.assertEqual([c["text"] for c in result["cells"]],
                         ["-", None, "-8,137,823,726.59"])
        self.assertEqual(result["cells"][2]["column_index"], 2)
        self.assertFalse(result["column_ownership_verified"])

    def test_rejects_misaligned_geometry(self):
        with self.assertRaisesRegex(ValueError, "column count"):
            self.extract([["1", "2"]], [[(0, 0, 1, 1)]])

    def test_rejects_nonfinite_geometry(self):
        with self.assertRaisesRegex(ValueError, "rectangle"):
            self.extract([["1"]], [[(0, 0, float("inf"), 1)]])

    def test_rejects_invalid_pages_before_opening(self):
        for pages in ([], [True], [1, 1], [0]):
            with self.subTest(pages=pages), self.assertRaises(ValueError):
                extract_table_cells("missing.pdf", "000776.SZ", "2026-10-30", pages)
