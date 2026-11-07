import hashlib
import tempfile
import unittest
from pathlib import Path

from scripts.disclosure_pdf_text_evidence import build_text_evidence


class DisclosurePdfTextEvidenceTests(unittest.TestCase):
    url = "https://static.cninfo.com.cn/finalpage/2026-10-20/report.pdf"
    pdf = b"%PDF-1.4\nsynthetic local pdf\n%%EOF"

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        originals = Path(self.tmp.name) / "originals"
        originals.mkdir()
        (originals / "report.pdf").write_bytes(self.pdf)
        self.digest = hashlib.sha256(self.pdf).hexdigest()
        self.snapshot = {
            "source": "cninfo",
            "source_content_verified": False,
            "historical_point_in_time_verified": False,
            "records": [{"symbol": "000776.SZ", "announcement_date": "2026-10-20",
                         "url": self.url, "pdf_artifact": {
                             "source_url": self.url, "sha256": self.digest,
                         }}],
            "original_pdf_artifacts": [{
                "source_url": self.url, "relative_path": "originals/report.pdf",
                "sha256": self.digest, "retrieved_at": "2026-10-21T00:00:00+00:00",
                "official_origin_verified": False, "source_content_verified": False,
                "historical_point_in_time_verified": False,
            }],
        }
        self.requests = [{"source_url": self.url, "pages": [1]}]

    def extract(self, path, symbol, day, pages):
        return [{"file_sha256": self.digest, "page": 1, "text": "营业收入 123",
                 "text_extraction_status": "text_extracted_unverified"}]

    def test_links_page_text_to_source_url_hash_retrieval_and_page(self):
        result = build_text_evidence(self.snapshot, self.tmp.name, self.requests,
                                     extract_pages_fn=self.extract)
        page = result["pages"][0]
        self.assertEqual(page["source_url"], self.url)
        self.assertEqual(page["file_sha256"], self.digest)
        self.assertEqual(page["retrieved_at"], "2026-10-21T00:00:00+00:00")
        self.assertEqual(page["page"], 1)
        self.assertEqual(page["text"], "营业收入 123")
        self.assertFalse(result["all_pages_verified"])
        self.assertFalse(page["financial_meaning_verified"])

    def test_rejects_file_that_differs_from_manifest_hash(self):
        Path(self.tmp.name, "originals", "report.pdf").write_bytes(self.pdf + b" tampered")
        with self.assertRaisesRegex(ValueError, "hash does not match"):
            build_text_evidence(self.snapshot, self.tmp.name, self.requests,
                                extract_pages_fn=self.extract)

    def test_rejects_manifest_path_traversal_and_symlink(self):
        self.snapshot["original_pdf_artifacts"][0]["relative_path"] = "../outside.pdf"
        with self.assertRaisesRegex(ValueError, "inside output directory"):
            build_text_evidence(self.snapshot, self.tmp.name, self.requests,
                                extract_pages_fn=self.extract)
        self.snapshot["original_pdf_artifacts"][0]["relative_path"] = "originals/report.pdf"
        target = Path(self.tmp.name, "originals", "report.pdf")
        target.unlink()
        target.symlink_to(Path(self.tmp.name) / "outside.pdf")
        Path(self.tmp.name, "outside.pdf").write_bytes(self.pdf)
        with self.assertRaisesRegex(ValueError, "inside output directory"):
            build_text_evidence(self.snapshot, self.tmp.name, self.requests,
                                extract_pages_fn=self.extract)

    def test_rejects_unknown_duplicate_or_verified_evidence_inputs(self):
        for requests in ([], self.requests * 2,
                         [{"source_url": "https://example.com/a.pdf", "pages": [1]}]):
            with self.subTest(requests=requests), self.assertRaises(ValueError):
                build_text_evidence(self.snapshot, self.tmp.name, requests,
                                    extract_pages_fn=self.extract)
        changed = dict(self.snapshot, source_content_verified=True)
        with self.assertRaisesRegex(ValueError, "unverified"):
            build_text_evidence(changed, self.tmp.name, self.requests,
                                extract_pages_fn=self.extract)

    def test_rejects_mismatched_page_extractor_hash(self):
        def bad_extract(*args):
            return [{"file_sha256": "0" * 64, "page": 1, "text": "x",
                     "text_extraction_status": "text_extracted_unverified"}]
        with self.assertRaisesRegex(ValueError, "extracted page hash"):
            build_text_evidence(self.snapshot, self.tmp.name, self.requests,
                                extract_pages_fn=bad_extract)

    def test_rejects_overwide_page_request(self):
        too_many = [{"source_url": self.url, "pages": list(range(1, 102))}]
        with self.assertRaisesRegex(ValueError, "at most 100 pages"):
            build_text_evidence(self.snapshot, self.tmp.name, too_many,
                                extract_pages_fn=self.extract)


if __name__ == "__main__":
    unittest.main()
