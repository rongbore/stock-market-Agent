"""End-to-end offline evidence flow using a valid synthetic PDF and real pdfplumber."""
import json
import tempfile
import unittest
from pathlib import Path

from scripts.pdf_sample_bundle_cli import main as bundle_main
from scripts.pdf_review_offline_cli import main as review_main
from test_offline_pdf_rectangle_integration import make_pdf_with_rectangle


SOURCE = "https://static.cninfo.com.cn/finalpage/2026-03-31/1225060422.PDF"


class PdfBundleReviewEndToEndTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.pdf = self.root / "synthetic.pdf"
        self.pdf.write_bytes(make_pdf_with_rectangle())
        self.bundle = self.root / "bundle.json"
        self.manifest = self.root / "manifest.json"
        self.annotations = self.root / "annotations.json"
        self.review = self.root / "review.json"

    def create_bundle(self):
        self.assertEqual(bundle_main([
            "--pdf", str(self.pdf), "--symbol", "000776.SZ",
            "--announcement-date", "2026-03-31",
            "--source-url", SOURCE, "--pages", "1",
            "--output", str(self.bundle),
        ]), 0)
        data = json.loads(self.bundle.read_text(encoding="utf-8"))
        self.manifest.write_text(
            json.dumps(data["review_manifest"]), encoding="utf-8")
        return data

    def create_annotations(self, manifest, *, fingerprint=None, bbox=None):
        candidate = manifest["candidates"][0]
        self.annotations.write_text(json.dumps({
            "file_sha256": fingerprint or manifest["file_sha256"],
            "decisions": [{
                "candidate_index": 0,
                "page": candidate["page"],
                "bbox": candidate["bbox"] if bbox is None else bbox,
                "review_status": "accepted_by_reviewer",
                "reviewer": "Test Reviewer",
            }],
        }), encoding="utf-8")

    def validate(self):
        return review_main([
            "--manifest", str(self.manifest),
            "--annotations", str(self.annotations),
            "--output", str(self.review),
        ])

    def test_full_workflow_preserves_sha_and_unverified_status(self):
        bundle = self.create_bundle()
        manifest = bundle["review_manifest"]
        self.assertEqual(manifest["candidate_count"], 1)
        self.assertEqual(manifest["candidates"][0]["bbox"], [20, 120, 240, 220])
        self.assertEqual(bundle["source_record"]["file_sha256"], manifest["file_sha256"])
        self.create_annotations(manifest)
        self.assertEqual(self.validate(), 0)
        review = json.loads(self.review.read_text(encoding="utf-8"))
        self.assertTrue(review["review_complete"])
        self.assertEqual(review["file_sha256"], bundle["source_record"]["file_sha256"])
        self.assertFalse(review["official_origin_verified"])
        self.assertFalse(review["financial_meaning_verified"])
        self.assertFalse(bundle["source_record"]["source_file_match_verified"])

    def test_stale_pdf_fingerprint_blocks_review_output(self):
        manifest = self.create_bundle()["review_manifest"]
        self.create_annotations(manifest, fingerprint="b" * 64)
        with self.assertRaisesRegex(ValueError, "fingerprint"):
            self.validate()
        self.assertFalse(self.review.exists())

    def test_modified_candidate_bbox_blocks_review_output(self):
        manifest = self.create_bundle()["review_manifest"]
        self.create_annotations(manifest, bbox=[21, 120, 240, 220])
        with self.assertRaisesRegex(ValueError, "coordinates"):
            self.validate()
        self.assertFalse(self.review.exists())


if __name__ == "__main__":
    unittest.main()
