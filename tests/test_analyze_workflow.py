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

    def test_input_preflight_precedes_paid_analysis_and_install(self):
        workflow = (Path(__file__).resolve().parents[1] /
                    ".github/workflows/analyze.yml").read_text(encoding="utf-8")
        preflight = workflow.index("      - name: Validate analysis inputs before dependency install\n")
        install = workflow.index("      - name: Install pinned TradingAgents\n")
        analyze = workflow.index("      - name: Analyze stock\n")
        self.assertLess(preflight, install)
        self.assertLess(install, analyze)
        preflight_section = workflow[preflight:install]
        self.assertIn("from scripts.analyze import read_inputs", preflight_section)
        self.assertNotIn("DEEPSEEK_API_KEY", preflight_section)

    def test_manual_workflow_defaults_to_no_cost_offline_smoke(self):
        workflow = (Path(__file__).resolve().parents[1] /
                    ".github/workflows/analyze.yml").read_text(encoding="utf-8")
        dry_run_section = workflow.split("      dry_run:", 1)[1].split("      model:", 1)[0]
        self.assertIn("type: boolean", dry_run_section)
        self.assertIn("default: true", dry_run_section)
        self.assertIn("if: ${{ !inputs.dry_run }}", workflow)
        self.assertIn("if: ${{ inputs.dry_run }}", workflow)

    def test_manual_dispatch_only(self):
        workflow = (Path(__file__).resolve().parents[1] /
                    ".github/workflows/analyze.yml").read_text(encoding="utf-8")
        self.assertIn("  workflow_dispatch:", workflow)
        self.assertNotIn("\n  schedule:", workflow)


if __name__ == "__main__":
    unittest.main()
