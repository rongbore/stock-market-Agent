import json
import tempfile
import unittest
from pathlib import Path

from scripts.pdf_review_offline_cli import main, validate_review_files


class PdfReviewOfflineCliTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        root = Path(self.temp.name)
        self.manifest = root / "manifest.json"
        self.annotations = root / "annotations.json"
        self.output = root / "validated.json"
        self.manifest.write_text(json.dumps({
            "file_sha256": "a" * 64,
            "candidates": [{"page": 1, "bbox": [20, 120, 240, 220]}],
        }), encoding="utf-8")
        self.annotations.write_text(json.dumps({
            "file_sha256": "a" * 64,
            "decisions": [{"candidate_index": 0, "page": 1,
                           "bbox": [20, 120, 240, 220],
                           "review_status": "accepted_by_reviewer",
                           "reviewer": "Auditor"}],
        }), encoding="utf-8")

    def test_cli_writes_unverified_report(self):
        self.assertEqual(main([
            "--manifest", str(self.manifest),
            "--annotations", str(self.annotations),
            "--output", str(self.output),
        ]), 0)
        result = json.loads(self.output.read_text(encoding="utf-8"))
        self.assertTrue(result["review_complete"])
        self.assertFalse(result["financial_meaning_verified"])
        self.assertFalse(result["official_origin_verified"])

    def test_rejects_changed_pdf_hash_without_output(self):
        data = json.loads(self.annotations.read_text(encoding="utf-8"))
        data["file_sha256"] = "b" * 64
        self.annotations.write_text(json.dumps(data), encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "fingerprint"):
            main(["--manifest", str(self.manifest),
                  "--annotations", str(self.annotations),
                  "--output", str(self.output)])
        self.assertFalse(self.output.exists())

    def test_rejects_input_overwrite(self):
        with self.assertRaisesRegex(ValueError, "overwrite"):
            main(["--manifest", str(self.manifest),
                  "--annotations", str(self.annotations),
                  "--output", str(self.manifest)])

    def test_rejects_non_object_json(self):
        self.annotations.write_text("[]", encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "object"):
            validate_review_files(self.manifest, self.annotations)

    def test_rejects_oversized_json(self):
        self.annotations.write_text(" " * (1024 * 1024 + 1), encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "oversized"):
            validate_review_files(self.manifest, self.annotations)


if __name__ == "__main__":
    unittest.main()
