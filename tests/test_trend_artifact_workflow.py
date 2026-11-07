"""Offline workflow contract for report artifacts; no market calls."""
import unittest
from pathlib import Path


class TrendArtifactWorkflowTests(unittest.TestCase):
    def test_workflow_wires_two_source_snapshots(self):
        workflow = Path(".github/workflows/akshare-dual-crosscheck.yml").read_text(encoding="utf-8")
        self.assertIn("python -m scripts.market_trend_report", workflow)
        self.assertIn("--primary dual_output/eastmoney_daily_unverified.json", workflow)
        self.assertIn("--secondary dual_output/sina_daily_unverified.json", workflow)
        self.assertIn("--comparison dual_output/daily_crosscheck_report.json", workflow)

    def test_workflow_uploads_html_and_reacts_to_code_changes(self):
        workflow = Path(".github/workflows/akshare-dual-crosscheck.yml").read_text(encoding="utf-8")
        self.assertIn("dual_output/*.html", workflow)
        self.assertIn("'scripts/market_trend_report.py'", workflow)
        self.assertIn("'scripts/trend_chart_overlay.py'", workflow)
        self.assertIn("'scripts/trend_indicators.py'", workflow)

    def test_missing_snapshots_are_skipped(self):
        workflow = Path(".github/workflows/akshare-dual-crosscheck.yml").read_text(encoding="utf-8")
        self.assertIn("Trend charts skipped", workflow)
        self.assertIn("[ -f dual_output/daily_crosscheck_report.json ]", workflow)


if __name__ == "__main__":
    unittest.main()
