"""Real-parser end-to-end test for the unverified PDF review manifest."""
import hashlib
import tempfile
import unittest
from pathlib import Path

from scripts.pdf_rectangle_review_manifest import build_review_manifest
from test_offline_pdf_rectangle_integration import make_pdf_with_rectangle


class PdfReviewManifestRealParserTests(unittest.TestCase):
    def test_manifest_preserves_pdf_fingerprint_and_unverified_bbox(self):
        try:
            import pdfplumber  # noqa: F401
        except ImportError:
            self.skipTest("optional pdfplumber is not installed")
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "drawn-rectangle.pdf"
            contents = make_pdf_with_rectangle()
            path.write_bytes(contents)
            manifest = build_review_manifest(
                path, "000776.SZ", "2026-10-20", [1])
        self.assertEqual(manifest["file_sha256"], hashlib.sha256(contents).hexdigest())
        self.assertEqual(manifest["pages_requested"], [1])
        self.assertEqual(manifest["candidate_count"], 1)
        self.assertEqual(manifest["candidates"][0]["bbox"], [20, 120, 240, 220])
        self.assertEqual(manifest["candidates"][0]["review_status"], "pending_manual_review")
        self.assertFalse(manifest["candidates"][0]["is_financial_table_verified"])
        self.assertFalse(manifest["official_origin_verified"])
        self.assertFalse(manifest["table_boundaries_verified"])
        self.assertFalse(manifest["financial_meaning_verified"])


if __name__ == "__main__":
    unittest.main()
