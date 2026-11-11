"""Independent real-parser checks for financial data through the dashboard CLI."""
import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from scripts.financial_review_pipeline import build_financial_review_artifact
from tests.test_financial_table_review_integration import synthetic_table_pdf


@unittest.skipUnless(importlib.util.find_spec("pdfplumber"), "optional pdfplumber not installed")
class FinancialDashboardIntegrationTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.pdf = self.root / "synthetic.pdf"
        self.pdf.write_bytes(synthetic_table_pdf())
        self.config = self.root / "configs" / "financial.json"
        self.config.parent.mkdir()
        self.output = self.root / "dashboard.html"
        self.settings = {"schema_version": "0.1", "data_kind": "SYNTHETIC", "pdf_path": "../synthetic.pdf",
                         "symbol": "000776.SZ", "announcement_date": "2026-10-30", "pages": [1],
                         "annotations": None}

    def run_cli(self, output=None):
        self.config.write_text(json.dumps(self.settings), encoding="utf-8")
        return subprocess.run([sys.executable, "-m", "scripts.offline_research_dashboard",
                               "--financial-config", str(self.config), "--output", str(output or self.output)],
                              cwd=Path(__file__).resolve().parents[1], capture_output=True, text=True, timeout=30)

    def test_relative_config_pdf_path_runs_real_parser_without_disclosing_local_path(self):
        result = self.run_cli()
        self.assertEqual(result.returncode, 0, result.stderr)
        html = self.output.read_text()
        evidence = build_financial_review_artifact(self.pdf, "000776.SZ", "2026-10-30", [1])
        self.assertIn("000776.SZ", html)
        self.assertIn("-8,137.59", html)
        self.assertIn(evidence["package"]["file_sha256"], html)
        self.assertIn(evidence["validation"]["package_sha256"], html)
        self.assertNotIn(str(self.root), html)
        self.assertIn("未核验", html)

    def test_stale_annotations_preserve_existing_output(self):
        self.settings["annotations"] = {"file_sha256": "a"*64, "package_sha256": "b"*64, "decisions": []}
        self.output.write_text("preserve")
        result = self.run_cli()
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(self.output.read_text(), "preserve")

    def test_output_cannot_replace_referenced_pdf_or_hardlink_alias(self):
        original = self.pdf.read_bytes()
        for target in (self.pdf, self.root / "alias.pdf"):
            if target != self.pdf:
                target.hardlink_to(self.pdf)
            with self.subTest(target=target.name):
                result = self.run_cli(target)
                self.assertNotEqual(result.returncode, 0)
                self.assertEqual(self.pdf.read_bytes(), original)

    def test_empty_numeric_evidence_can_be_displayed_without_fabricated_values(self):
        self.pdf.write_bytes(synthetic_table_pdf([
            ("", "本报告期", "年初至报告期末"), ("营业总收入（元）", "-", "-"),
            ("总资产（元）", "-", "-")]))
        result = self.run_cli()
        self.assertEqual(result.returncode, 0, result.stderr)
        html = self.output.read_text()
        self.assertNotIn("-8,137.59", html)
        self.assertIn("未核验", html)
        self.assertIn("no_numeric_candidates", html)
