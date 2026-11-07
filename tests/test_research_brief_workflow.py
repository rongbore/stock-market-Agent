"""Verify that offline research briefs are wired into dual-source artifacts."""
import unittest
from pathlib import Path


class ResearchBriefWorkflowTests(unittest.TestCase):
    def test_brief_runs_after_trend_generation(self):
        text = Path(".github/workflows/akshare-dual-crosscheck.yml").read_text(encoding="utf-8")
        self.assertIn("python -m scripts.market_research_brief", text)
        self.assertIn("--trend-data dual_output/price_trend_data.json", text)
        self.assertIn("--output-dir dual_output", text)
        self.assertLess(text.index("python -m scripts.market_trend_report"),
                        text.index("python -m scripts.market_research_brief"))

    def test_missing_trend_evidence_skips_brief(self):
        text = Path(".github/workflows/akshare-dual-crosscheck.yml").read_text(encoding="utf-8")
        self.assertIn("[ -f dual_output/price_trend_data.json ]", text)
        self.assertIn("Research brief skipped", text)

    def test_artifact_upload_includes_brief_formats(self):
        text = Path(".github/workflows/akshare-dual-crosscheck.yml").read_text(encoding="utf-8")
        self.assertIn("dual_output/*.json", text)
        self.assertIn("dual_output/*.md", text)
        self.assertIn("'scripts/market_research_brief.py'", text)


if __name__ == "__main__":
    unittest.main()
