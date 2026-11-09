import copy
import json
from pathlib import Path
import tempfile
import unittest

from scripts.financial_table_review_annotations import review_package_sha256
from scripts.financial_table_review_report import render_review_markdown, main


def package():
    return {"schema_version": "0.1", "status": "PENDING_MANUAL_VERIFICATION",
            "file_sha256": "a" * 64, "candidate_count": 2,
            "financial_meaning_verified": False,
            "candidates": [{"cell": {"text": "10.00", "page": 1, "table_index": 0,
                                      "row_index": 1, "column_index": 2},
                            "metric_hint_unverified": "revenue", "unit_hint_unverified": "CNY",
                            "period_hint_unverified": "year_to_date",
                            "review_blockers": ["consolidation_scope", "manual_verification"]},
                           {"cell": {"text": "-20.00"}, "review_blockers": ["metric"]}]}


class ReviewReportTests(unittest.TestCase):
    def test_partial_display_keeps_full_counts_and_blockers(self):
        original = package()
        before = copy.deepcopy(original)
        text = render_review_markdown(original, max_rows=1)
        self.assertIn("候选总数：2", text)
        self.assertIn("待记录决定：2", text)
        self.assertIn("未展示候选：1", text)
        self.assertIn("consolidation\\_scope", text)
        self.assertNotIn("-20.00", text)
        self.assertEqual(original, before)

    def test_untrusted_markdown_and_html_are_escaped(self):
        p = package()
        p["candidates"][0]["cell"]["text"] = "<script>x</script> | ![x](https://x)\nrow"
        text = render_review_markdown(p)
        self.assertNotIn("<script>", text)
        self.assertNotIn("![x]", text)
        self.assertIn("\\|", text)
        self.assertIn("&lt;script&gt;", text)

    def test_stale_annotations_cannot_appear_as_accepted(self):
        p = package()
        annotations = {"file_sha256": p["file_sha256"], "package_sha256": review_package_sha256(p),
                       "decisions": [{"candidate_index": 0, "decision": "accepted_by_reviewer",
                                      "reviewer": "A", "note": "Checked."}]}
        self.assertIn("已记录决定：1", render_review_markdown(p, annotations))
        p["candidates"][0]["cell"]["text"] = "99"
        with self.assertRaisesRegex(ValueError, "fingerprint"):
            render_review_markdown(p, annotations)

    def test_cli_writes_report_and_preserves_source(self):
        with tempfile.TemporaryDirectory() as directory:
            source, output = Path(directory)/"package.json", Path(directory)/"review.md"
            source.write_text(json.dumps(package()))
            original = source.read_bytes()
            main(["--package", str(source), "--output", str(output)])
            self.assertIn("未核验", output.read_text())
            with self.assertRaises(ValueError):
                main(["--package", str(source), "--output", str(source)])
            self.assertEqual(source.read_bytes(), original)

    def test_invalid_row_limit_rejected(self):
        for limit in (True, 0, 501):
            with self.subTest(limit=limit), self.assertRaises(ValueError):
                render_review_markdown(package(), max_rows=limit)
