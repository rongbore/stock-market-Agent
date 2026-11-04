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

    def test_disclosure_metadata_is_explicitly_unverified(self):
        diag = {"symbol": "000776.SZ", "start_date": "2026-10-01", "end_date": "2026-10-30", "status": "success"}
        text = render(diag, disclosures=[
            {"symbol": "000776.SZ", "announcement_date": "2026-10-20",
             "title": "季度报告（索引示例）"}])
        self.assertIn("公告索引元数据", text)
        self.assertIn("2026-10-20", text)
        self.assertIn("未核验公告原文", text)

    def test_disclosure_from_future_is_rejected(self):
        diag = {"symbol": "000776.SZ", "start_date": "2026-10-01", "end_date": "2026-10-30"}
        with self.assertRaisesRegex(ValueError, "outside research range"):
            render(diag, disclosures=[
                {"symbol": "000776.SZ", "announcement_date": "2026-11-01",
                 "title": "不可用于研究截止日"}])

    def test_disclosure_wrong_symbol_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "symbol mismatch"):
            render({"symbol": "000776.SZ", "start_date": "2026-10-01", "end_date": "2026-10-30"}, disclosures=[
                {"symbol": "000001.SZ", "announcement_date": "2026-10-20",
                 "title": "其他公司公告"}])

    def test_missing_disclosure_index_is_not_zero_disclosures(self):
        text = render({"symbol": "000776.SZ"})
        self.assertIn("不能推断该区间没有公告", text)

    def test_disclosure_before_start_is_rejected(self):
        diag = {"symbol": "000776.SZ", "start_date": "2026-10-01",
                "end_date": "2026-10-30"}
        with self.assertRaisesRegex(ValueError, "outside research range"):
            render(diag, disclosures=[
                {"symbol": "000776.SZ", "announcement_date": "2026-09-30",
                 "title": "不属于研究区间"}])

    def test_disclosure_title_is_escaped_as_untrusted_markdown(self):
        diag = {"symbol": "000776.SZ", "start_date": "2026-10-01",
                "end_date": "2026-10-30"}
        output = render(diag, disclosures=[
            {"symbol": "000776.SZ", "announcement_date": "2026-10-20",
             "title": "[click](https://example.com) | <script>"}])
        self.assertNotIn("[click](https://example.com)", output)
        self.assertNotIn("<script>", output)
        self.assertIn("公告索引元数据", output)

    def test_disclosure_requires_research_date_range(self):
        with self.assertRaisesRegex(ValueError, "research date range required"):
            render({"symbol": "000776.SZ"}, disclosures=[])

    def test_pdf_fingerprint_render_is_unverified(self):
        diag = {"symbol": "000776.SZ", "start_date": "2026-10-01",
                "end_date": "2026-10-30"}
        evidence = {"symbol": "000776.SZ", "announcement_date": "2026-10-20",
                    "file_sha256": "a" * 64, "file_size_bytes": 1024,
                    "official_origin_verified": False,
                    "source_content_verified": False}
        output = render(diag, fingerprints=[evidence])
        self.assertIn("SHA-256", output)
        self.assertIn("a" * 64, output)
        self.assertIn("不证明官方来源", output)

    def test_pdf_fingerprint_rejects_false_claims(self):
        diag = {"symbol": "000776.SZ", "start_date": "2026-10-01",
                "end_date": "2026-10-30"}
        evidence = {"symbol": "000776.SZ", "announcement_date": "2026-10-20",
                    "file_sha256": "a" * 64, "file_size_bytes": 1024,
                    "official_origin_verified": True,
                    "source_content_verified": False}
        with self.assertRaisesRegex(ValueError, "verification claims"):
            render(diag, fingerprints=[evidence])

    def test_pdf_fingerprint_rejects_out_of_range_and_bad_hash(self):
        diag = {"symbol": "000776.SZ", "start_date": "2026-10-01",
                "end_date": "2026-10-30"}
        evidence = {"symbol": "000776.SZ", "announcement_date": "2026-09-30",
                    "file_sha256": "a" * 64, "file_size_bytes": 1024,
                    "official_origin_verified": False,
                    "source_content_verified": False}
        with self.assertRaisesRegex(ValueError, "outside research range"):
            render(diag, fingerprints=[evidence])
        evidence["announcement_date"] = "2026-10-20"
        evidence["file_sha256"] = "bad"
        with self.assertRaisesRegex(ValueError, "SHA-256"):
            render(diag, fingerprints=[evidence])

    def test_report_requires_diagnostic_object(self):
        with self.assertRaises(ValueError):
            render([])


if __name__ == "__main__":
    unittest.main()
