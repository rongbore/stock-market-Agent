"""Repository demo fixtures are synthetic and run all three offline panels."""
import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from tests.test_financial_table_review_integration import synthetic_table_pdf

ROOT = Path(__file__).resolve().parents[1]
FINANCIAL = ROOT / "examples/financial_review/SYNTHETIC_dashboard_config.json"


class DashboardDemoTests(unittest.TestCase):
    def test_committed_pdf_is_exactly_the_labelled_synthetic_generator_output(self):
        config = json.loads(FINANCIAL.read_text())
        self.assertEqual(config["data_kind"], "SYNTHETIC")
        self.assertIsNone(config["annotations"])
        rows = [("合成测试数据", "本报告期", "年初至报告期末"),
                ("营业总收入（元）", "10.00", "30.00"),
                ("经营活动产生的现金流量净额（元）", "-", "-8,137.59")]
        self.assertEqual((FINANCIAL.parent / config["pdf_path"]).read_bytes(), synthetic_table_pdf(rows))

    @unittest.skipUnless(importlib.util.find_spec("pdfplumber"), "optional pdfplumber not installed")
    def test_documented_three_panel_command_is_deterministic_without_mocking(self):
        with tempfile.TemporaryDirectory() as folder:
            outputs = [Path(folder)/"first.html", Path(folder)/"second.html"]
            for output in outputs:
                result = subprocess.run([
                    sys.executable, "-m", "scripts.offline_research_dashboard",
                    "--batch-config", "examples/batch_research/SYNTHETIC_offline_pipeline.json",
                    "--evaluation-config", "examples/backtest/SYNTHETIC_sma_oos_config.json",
                    "--financial-config", str(FINANCIAL), "--output", str(output)],
                    cwd=ROOT, capture_output=True, text=True, timeout=30)
                self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(outputs[0].read_bytes(), outputs[1].read_bytes())
            html = outputs[0].read_text()
            for text in ("批量研究任务", "样本外纸面评估", "财报证据复核", "-8,137.59", "未核验"):
                self.assertIn(text, html)
            self.assertIn("<svg", html)
            self.assertNotIn("<script", html)
            self.assertNotIn(str(FINANCIAL.parent), html)
