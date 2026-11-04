import tempfile
import unittest
from pathlib import Path

from scripts.pdf_rectangle_review_manifest import build_review_manifest


class FakePdf:
    def __init__(self, rects):
        self.pages = [type("Page", (), {"rects": rects})()]

    def __enter__(self):
        return self

    def __exit__(self, *_):
        return False


class PdfRectangleReviewManifestTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.pdf = Path(self.tmp.name) / "filing.pdf"
        self.pdf.write_bytes(b"%PDF-1.4\nsynthetic fixture\n%%EOF")

    def make_manifest(self, rectangles):
        return build_review_manifest(
            self.pdf, "000776.SZ", "2026-10-20", [1],
            opener=lambda _: FakePdf(rectangles))

    def test_candidate_requires_manual_review(self):
        report = self.make_manifest([
            {"x0": 10, "top": 20, "x1": 300, "bottom": 200}])
        self.assertEqual(report["candidate_count"], 1)
        self.assertEqual(report["candidates"][0]["review_status"], "pending_manual_review")
        self.assertFalse(report["candidates"][0]["is_financial_table_verified"])
        self.assertFalse(report["official_origin_verified"])
        self.assertFalse(report["financial_meaning_verified"])
        self.assertEqual(len(report["file_sha256"]), 64)

    def test_empty_page_does_not_imply_verified(self):
        report = self.make_manifest([])
        self.assertEqual(report["candidate_count"], 0)
        self.assertFalse(report["table_boundaries_verified"])

    def test_overlapping_regions_are_reported_not_accepted(self):
        report = self.make_manifest([
            {"x0": 0, "top": 0, "x1": 300, "bottom": 200},
            {"x0": 100, "top": 100, "x1": 350, "bottom": 250},
        ])
        self.assertEqual(report["candidate_count"], 0)
        self.assertEqual(report["ambiguous_overlap_count"], 2)

    def test_invalid_pdf_header_is_rejected(self):
        self.pdf.write_bytes(b"not a pdf file")
        with self.assertRaises(ValueError):
            self.make_manifest([])


if __name__ == "__main__":
    unittest.main()
