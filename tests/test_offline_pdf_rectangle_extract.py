import tempfile
import unittest
from pathlib import Path

from scripts.offline_pdf_rectangle_extract import extract_rectangle_candidates


class FakePdf:
    def __init__(self, rectangles):
        self.pages = [type("Page", (), {"rects": rectangles})()]

    def __enter__(self):
        return self

    def __exit__(self, *_):
        return False


def rect(x0=10, top=20, x1=300, bottom=200):
    return {"x0": x0, "top": top, "x1": x1, "bottom": bottom}


class OfflinePdfRectangleTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.file = Path(self.tmp.name) / "sample.pdf"
        self.file.write_bytes(b"%PDF-1.4\nsynthetic fixture\n%%EOF")

    def extract(self, rectangles, pages=None):
        return extract_rectangle_candidates(
            self.file, "000776.SZ", "2026-10-20",
            [1] if pages is None else pages,
            opener=lambda _: FakePdf(rectangles))

    def test_extracts_candidate_without_verification(self):
        result = self.extract([rect()])
        self.assertEqual(result["regions"][0]["bbox"], [10, 20, 300, 200])
        self.assertFalse(result["table_boundaries_verified"])
        self.assertFalse(result["official_origin_verified"])

    def test_rejects_page_out_of_range_and_duplicates(self):
        with self.assertRaisesRegex(ValueError, "out of range"):
            self.extract([], [2])
        with self.assertRaisesRegex(ValueError, "duplicate"):
            self.extract([], [1, 1])

    def test_rejects_too_many_rectangles(self):
        with self.assertRaisesRegex(ValueError, "too many"):
            self.extract([rect()] * 2001)

    def test_rejects_invalid_coordinate(self):
        with self.assertRaisesRegex(ValueError, "coordinate"):
            self.extract([rect(x1=float("nan"))])

    def test_rejects_invalid_pdf_header(self):
        self.file.write_bytes(b"not a pdf file")
        with self.assertRaisesRegex(ValueError, "PDF header"):
            self.extract([])

    def test_empty_page_has_no_candidates(self):
        self.assertEqual(self.extract([])["regions"], [])


if __name__ == "__main__":
    unittest.main()
