"""Static contract for the explicit no-API workflow smoke mode."""
import unittest
from pathlib import Path


class OfflineWorkflowSmokeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.workflow = (Path(__file__).resolve().parents[1] /
                        ".github/workflows/analyze.yml").read_text(encoding="utf-8")

    def test_dry_run_is_explicit_and_defaults_on(self):
        self.assertIn("      dry_run:", self.workflow)
        self.assertIn("        type: boolean", self.workflow)
        self.assertIn("        default: true", self.workflow)

    def test_real_analysis_is_skipped_in_dry_run(self):
        self.assertIn("  analyze:\n    if: ${{ !inputs.dry_run }}", self.workflow)
        self.assertIn("  offline-smoke:\n    if: ${{ inputs.dry_run }}", self.workflow)

    def test_synthetic_path_checks_and_uploads(self):
        smoke = self.workflow.split("  offline-smoke:\n", 1)[1]
        self.assertIn("OFFLINE SYNTHETIC TEST ONLY", smoke)
        self.assertIn("python scripts/report_contract.py results/reports", smoke)
        self.assertIn("python scripts/artifact_secret_guard.py results/reports", smoke)
        self.assertIn("offline-synthetic-smoke-", smoke)
        self.assertNotIn("DEEPSEEK_API_KEY", smoke)
        self.assertNotIn("tradingagents @", smoke)


if __name__ == "__main__":
    unittest.main()
