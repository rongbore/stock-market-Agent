import tempfile
import unittest
from pathlib import Path

from scripts.report_contract import validate_report_directory, validate_reports_root


class ReportContractTests(unittest.TestCase):
    def test_missing_directory(self):
        with tempfile.TemporaryDirectory() as tmp:
            self.assertTrue(validate_reports_root(Path(tmp) / "missing"))

    def test_missing_report(self):
        with tempfile.TemporaryDirectory() as tmp:
            self.assertTrue(validate_report_directory(tmp))

    def test_empty_report(self):
        with tempfile.TemporaryDirectory() as tmp:
            (Path(tmp) / "complete_report.html").write_text("", encoding="utf-8")
            self.assertIn("complete_report.html is empty", validate_report_directory(tmp))

    def test_whitespace_report(self):
        with tempfile.TemporaryDirectory() as tmp:
            (Path(tmp) / "complete_report.html").write_text("  \n", encoding="utf-8")
            self.assertTrue(validate_report_directory(tmp))

    def test_valid_report(self):
        with tempfile.TemporaryDirectory() as tmp:
            nested = Path(tmp) / "NVDA" / "2026-11-04"
            nested.mkdir(parents=True)
            (nested / "complete_report.html").write_text(
                "<!doctype html><html><body>Report</body></html>", encoding="utf-8"
            )
            self.assertEqual(validate_reports_root(tmp), [])

    def test_non_html_report(self):
        with tempfile.TemporaryDirectory() as tmp:
            (Path(tmp) / "complete_report.html").write_text("not HTML", encoding="utf-8")
            self.assertTrue(validate_report_directory(tmp))


if __name__ == "__main__":
    unittest.main()
