import tempfile
import unittest
from pathlib import Path

from scripts.offline_pdf_geometry_extract import extract_geometry


class FakePdf:
    def __init__(self, chars):
        self.pages = [type("Page", (), {"chars": chars})()]

    def __enter__(self):
        return self

    def __exit__(self, *_):
        return False


class OfflinePdfGeometryExtractTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.file = Path(self.tmp.name) / "sample.pdf"
        self.file.write_bytes(b"%PDF-1.4\nsynthetic fixture\n%%EOF")

    def extract(self, chars, pages=None):
        return extract_geometry(
            self.file, "000776.SZ", "2026-10-20",
            [1] if pages is None else pages,
            opener=lambda _: FakePdf(chars),
        )

    def test_extracts_unverified_character_positions(self):
        result = self.extract([{"text": "1", "x0": 10, "top": 20,
                                "x1": 15, "bottom": 30}])
        self.assertEqual(result["spans"][0]["bbox"], [10, 20, 15, 30])
        self.assertFalse(result["column_ownership_verified"])
        self.assertFalse(result["official_origin_verified"])

    def test_rejects_nonfinite_coordinates(self):
        with self.assertRaisesRegex(ValueError, "coordinate"):
            self.extract([{"text": "1", "x0": float("nan"), "top": 0,
                           "x1": 2, "bottom": 3}])

    def test_rejects_page_out_of_range_and_duplicates(self):
        with self.assertRaisesRegex(ValueError, "out of range"):
            self.extract([], [2])
        with self.assertRaisesRegex(ValueError, "duplicate"):
            self.extract([], [1, 1])

    def test_rejects_too_many_characters(self):
        chars = [{"text": "a", "x0": 0, "top": 0, "x1": 1, "bottom": 1}] * 2001
        with self.assertRaisesRegex(ValueError, "too many"):
            self.extract(chars)

    def test_rejects_invalid_pdf_header(self):
        self.file.write_bytes(b"not a pdf file")
        with self.assertRaisesRegex(ValueError, "PDF header"):
            self.extract([])


if __name__ == "__main__":
    unittest.main()
