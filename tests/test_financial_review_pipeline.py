import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from scripts.financial_review_pipeline import build_financial_review_artifact, main
from tests.test_financial_table_review_integration import synthetic_table_pdf


@unittest.skipUnless(importlib.util.find_spec("pdfplumber"), "optional pdfplumber not installed")
class ReviewPipelineTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.pdf = Path(self.tmp.name)/"synthetic.pdf"
        self.pdf.write_bytes(synthetic_table_pdf())

    def args(self, output):
        return ["--pdf", str(self.pdf), "--symbol", "000776.SZ", "--announcement-date",
                "2026-10-30", "--pages", "1", "--output", str(output)]

    def test_cli_real_parser_creates_one_complete_unverified_artifact(self):
        output = Path(self.tmp.name)/"review.json"
        main(self.args(output))
        artifact = json.loads(output.read_text())
        self.assertEqual(artifact["package"]["candidate_count"], 3)
        self.assertTrue(artifact["validation"]["structure_valid"])
        self.assertEqual(artifact["validation"]["package_sha256"], artifact["review_record"]["package_sha256"])
        self.assertIn(artifact["package"]["file_sha256"], artifact["report_markdown"])
        self.assertEqual(artifact["review_record"]["pending_count"], 3)
        self.assertFalse(artifact["release_evidence_accepted"])
        self.assertEqual(sorted(p.name for p in Path(self.tmp.name).iterdir()), ["review.json", "synthetic.pdf"])

    def test_bound_annotations_display_without_promoting_verification(self):
        artifact = build_financial_review_artifact(self.pdf, "000776.SZ", "2026-10-30", [1])
        annotations = {"file_sha256": artifact["package"]["file_sha256"],
                       "package_sha256": artifact["validation"]["package_sha256"],
                       "decisions": [{"candidate_index": 0, "decision": "accepted_by_reviewer",
                                      "reviewer": "Reviewer", "note": "Page examined."}]}
        reviewed = build_financial_review_artifact(self.pdf, "000776.SZ", "2026-10-30", [1], annotations=annotations)
        self.assertEqual(reviewed["review_record"]["decided_count"], 1)
        self.assertIn("accepted\\_by\\_reviewer", reviewed["report_markdown"])
        self.assertFalse(reviewed["financial_meaning_verified"])
        self.assertFalse(reviewed["review_record"]["release_evidence_accepted"])

    def test_stale_annotations_leave_existing_output_untouched(self):
        annotations = Path(self.tmp.name)/"annotations.json"
        annotations.write_text(json.dumps({"file_sha256": "a"*64, "package_sha256": "b"*64, "decisions": []}))
        output = Path(self.tmp.name)/"review.json"
        output.write_text("preserve")
        with self.assertRaisesRegex(ValueError, "fingerprint"):
            main(self.args(output) + ["--annotations", str(annotations)])
        self.assertEqual(output.read_text(), "preserve")

    def test_empty_numeric_table_is_not_materials_ready(self):
        self.pdf.write_bytes(synthetic_table_pdf([
            ("", "本报告期", "年初至报告期末"),
            ("营业总收入（元）", "-", "-"), ("总资产（元）", "-", "-")]))
        result = build_financial_review_artifact(self.pdf, "000776.SZ", "2026-10-30", [1])
        self.assertEqual(result["status"], "NO_NUMERIC_EVIDENCE")
        self.assertFalse(result["review_record"]["all_candidates_decided"])
        self.assertIn("no_numeric_candidates", result["package"]["review_blockers"])

    def test_final_file_change_and_source_overwrite_are_rejected(self):
        with patch("scripts.financial_review_pipeline._pdf_digest", return_value="0"*64):
            with self.assertRaisesRegex(ValueError, "changed"):
                build_financial_review_artifact(self.pdf, "000776.SZ", "2026-10-30", [1])
        original = self.pdf.read_bytes()
        with self.assertRaisesRegex(ValueError, "overwrite"):
            main(self.args(self.pdf))
        self.assertEqual(self.pdf.read_bytes(), original)

    def test_repeated_runs_are_deterministic(self):
        one = build_financial_review_artifact(self.pdf, "000776.SZ", "2026-10-30", [1])
        two = build_financial_review_artifact(self.pdf, "000776.SZ", "2026-10-30", [1])
        self.assertEqual(one, two)

    def test_explicit_null_or_duplicate_annotation_json_is_not_silently_ignored(self):
        annotations = Path(self.tmp.name)/"annotations.json"
        output = Path(self.tmp.name)/"review.json"
        output.write_text("preserve")
        for raw in ('null', '{"decisions": [], "decisions": []}'):
            annotations.write_text(raw)
            with self.subTest(raw=raw), self.assertRaises(ValueError):
                main(self.args(output) + ["--annotations", str(annotations)])
            self.assertEqual(output.read_text(), "preserve")
