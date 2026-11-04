import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from scripts.akshare_integration_check import run, main


class AKShareIntegrationCheckTests(unittest.TestCase):
    def test_success_report_does_not_claim_verification(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = str(Path(tmp) / "daily.json")
            with patch("scripts.akshare_integration_check.fetch_a_share_daily",
                       return_value={"records": [{"date": "2026-10-29"}],
                                     "source_content_verified": False}):
                report = run("000776.SZ", "2026-10-01", "2026-10-30", path)
            self.assertEqual(report["status"], "success")
            self.assertEqual(report["record_count"], 1)
            self.assertFalse(report["source_content_verified"])
            self.assertTrue(Path(path).exists())

    def test_failure_report_omits_exception_text(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = str(Path(tmp) / "daily.json")
            with patch("scripts.akshare_integration_check.fetch_a_share_daily",
                       side_effect=RuntimeError("SECRET-TOKEN")):
                report = run("000776.SZ", "2026-10-01", "2026-10-30", path)
            self.assertEqual(report["status"], "failed")
            self.assertNotIn("SECRET-TOKEN", str(report))
            self.assertFalse(Path(path).exists())


if __name__ == "__main__":
    unittest.main()
