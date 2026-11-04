import unittest
import json
import tempfile
from pathlib import Path
from scripts.akshare_evidence_report import render, main


class EvidenceReportTests(unittest.TestCase):
    def test_passed_comparison_does_not_claim_official_verification(self):
        diag = {"symbol": "000776.SZ", "start_date": "2026-10-01",
                "end_date": "2026-10-30", "status": "success",
                "eastmoney_record_count": 17, "sina_record_count": 17}
        report = {"status": "passed", "cross_source_numerical_agreement": True,
                  "difference_count": 0, "date_coverage": {"shared_trading_date_count": 17}}
        text = render(diag, report)
        self.assertIn("容差内通过", text)
        self.assertIn("官方数据认证 | 未认证", text)
        self.assertIn("共同交易日期：17", text)

    def test_partial_failure_does_not_claim_agreement(self):
        diag = {"symbol": "000776.SZ", "status": "failed",
                "error_category": "operating_system_or_network"}
        text = render(diag)
        self.assertIn("未通过或未完成", text)
        self.assertIn("未执行比较", text)
        self.assertIn("未核验财报", text)

    def test_offline_cli_creates_markdown_artifact(self):
        with tempfile.TemporaryDirectory() as temp:
            folder = Path(temp)
            diag = {"symbol": "000776.SZ", "status": "success",
                    "eastmoney_record_count": 17, "sina_record_count": 17}
            comparison = {"status": "passed",
                          "cross_source_numerical_agreement": True,
                          "difference_count": 0,
                          "date_coverage": {"shared_trading_date_count": 17}}
            (folder / "dual_upstream_diagnostics.json").write_text(
                json.dumps(diag), encoding="utf-8")
            (folder / "daily_crosscheck_report.json").write_text(
                json.dumps(comparison), encoding="utf-8")
            output = folder / "dual_source_evidence_unverified.md"
            self.assertEqual(main(["--input-dir", str(folder), "--output", str(output)]), 0)
            self.assertTrue(output.is_file())
            content = output.read_text(encoding="utf-8")
            self.assertIn("000776.SZ", content)
            self.assertIn("共同交易日期：17", content)
            self.assertIn("官方数据认证 | 未认证", content)

    def test_offline_cli_handles_failed_collection_without_comparison(self):
        with tempfile.TemporaryDirectory() as temp:
            folder = Path(temp)
            (folder / "dual_upstream_diagnostics.json").write_text(
                json.dumps({"symbol": "000776.SZ", "status": "failed"}),
                encoding="utf-8")
            output = folder / "dual_source_evidence_unverified.md"
            self.assertEqual(main(["--input-dir", str(folder), "--output", str(output)]), 0)
            content = output.read_text(encoding="utf-8")
            self.assertIn("未执行比较", content)
            self.assertIn("未通过或未完成", content)

    def test_report_requires_diagnostic_object(self):
        with self.assertRaises(ValueError):
            render([])


if __name__ == "__main__":
    unittest.main()
