"""Ensure the manual analysis workflow validates reports before upload."""
import unittest
from pathlib import Path


class AnalyzeWorkflowTests(unittest.TestCase):
    def test_validator_runs_after_analysis_and_before_upload(self):
        workflow = (Path(__file__).resolve().parents[1] /
                    ".github/workflows/analyze.yml").read_text(encoding="utf-8")
        analyze = workflow.index("      - name: Analyze stock\n")
        validate = workflow.index("      - name: Validate report artifacts\n")
        upload = workflow.index("      - name: Upload reports\n")
        self.assertLess(analyze, validate)
        self.assertLess(validate, upload)
        self.assertIn("run: python scripts/report_contract.py results/reports", workflow)
        self.assertIn("if-no-files-found: error", workflow)

    def test_manual_dispatch_only(self):
        workflow = (Path(__file__).resolve().parents[1] /
                    ".github/workflows/analyze.yml").read_text(encoding="utf-8")
        self.assertIn("  workflow_dispatch:", workflow)
        self.assertNotIn("\n  schedule:", workflow)


if __name__ == "__main__":
    unittest.main()
