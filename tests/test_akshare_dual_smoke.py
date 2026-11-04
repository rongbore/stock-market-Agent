import json
import tempfile
import unittest
from pathlib import Path

from scripts.akshare_dual_smoke import run


def snapshot(upstream, volume_unit, volume):
    return {"symbol": "000776.SZ", "upstream": upstream, "adjust": "",
            "start_date": "2026-10-01", "end_date": "2026-10-30",
            "volume_unit": volume_unit,
            "records": [{"date": "2026-10-08", "open": 19.8,
                         "high": 19.98, "low": 19.21, "close": 19.32,
                         "volume": volume}]}


class DualSmokeTests(unittest.TestCase):
    def test_sina_failure_keeps_eastmoney_snapshot_and_safe_diagnostics(self):
        def failing(*args):
            raise RuntimeError("secret token must never appear")
        with tempfile.TemporaryDirectory() as tmp:
            code = run("000776.SZ", "2026-10-01", "2026-10-30", tmp,
                       eastmoney=lambda *a: snapshot("eastmoney", "lots_100_shares", 432885),
                       sina=failing)
            self.assertEqual(code, 1)
            self.assertTrue((Path(tmp) / "eastmoney_daily_unverified.json").exists())
            diag = (Path(tmp) / "dual_upstream_diagnostics.json").read_text()
            self.assertEqual(json.loads(diag)["stage"], "sina")
            self.assertEqual(json.loads(diag)["error_category"], "runtime_or_dependency")
            self.assertNotIn("secret token", diag)

    def test_success_writes_comparison_and_diagnostics(self):
        with tempfile.TemporaryDirectory() as tmp:
            code = run("000776.SZ", "2026-10-01", "2026-10-30", tmp,
                       eastmoney=lambda *a: snapshot("eastmoney", "lots_100_shares", 432885),
                       sina=lambda *a: snapshot("sina", "shares", 43288500))
            self.assertEqual(code, 0)
            self.assertTrue((Path(tmp) / "daily_crosscheck_report.json").exists())
            diag = json.loads((Path(tmp) / "dual_upstream_diagnostics.json").read_text())
            self.assertEqual(diag["status"], "success")
            self.assertFalse(diag["independent_source_verified"])


    def test_price_mismatch_preserves_report_and_marks_mismatch(self):
        with tempfile.TemporaryDirectory() as tmp:
            def changed(*args):
                data = snapshot("sina", "shares", 43288500)
                data["records"][0]["close"] = 19.50
                return data
            code = run("000776.SZ", "2026-10-01", "2026-10-30", tmp,
                       eastmoney=lambda *a: snapshot("eastmoney", "lots_100_shares", 432885),
                       sina=changed)
            self.assertEqual(code, 1)
            report = json.loads((Path(tmp) / "daily_crosscheck_report.json").read_text())
            self.assertGreater(report["difference_count"], 0)
            self.assertFalse(report["cross_source_numerical_agreement"])
            diag = json.loads((Path(tmp) / "dual_upstream_diagnostics.json").read_text())
            self.assertEqual(diag["status"], "mismatch")
            self.assertEqual(diag["stage"], "complete")

    def test_eastmoney_failure_writes_safe_diagnostic_without_snapshots(self):
        def failing(*args):
            raise ConnectionError("private upstream request detail")
        with tempfile.TemporaryDirectory() as tmp:
            code = run("000776.SZ", "2026-10-01", "2026-10-30", tmp,
                       eastmoney=failing, sina=lambda *a: None)
            self.assertEqual(code, 1)
            diag_text = (Path(tmp) / "dual_upstream_diagnostics.json").read_text()
            self.assertEqual(json.loads(diag_text)["stage"], "eastmoney")
            self.assertEqual(json.loads(diag_text)["error_category"], "connection_or_timeout")
            self.assertNotIn("private upstream", diag_text)
            self.assertFalse((Path(tmp) / "sina_daily_unverified.json").exists())


    def test_eastmoney_failure_still_collects_sina_evidence(self):
        def unavailable(*args):
            raise OSError("secret request url should never appear")
        with tempfile.TemporaryDirectory() as tmp:
            code = run("000776.SZ", "2026-10-01", "2026-10-30", tmp,
                       eastmoney=unavailable,
                       sina=lambda *a: snapshot("sina", "shares", 43288500))
            self.assertEqual(code, 1)
            self.assertTrue((Path(tmp) / "sina_daily_unverified.json").exists())
            self.assertFalse((Path(tmp) / "daily_crosscheck_report.json").exists())
            raw = (Path(tmp) / "dual_upstream_diagnostics.json").read_text()
            diag = json.loads(raw)
            self.assertEqual(diag["stage"], "eastmoney")
            self.assertEqual(diag["eastmoney_status"], "failed")
            self.assertEqual(diag["sina_status"], "success")
            self.assertEqual(diag["sina_record_count"], 1)
            self.assertEqual(diag["eastmoney_error_kind"], "other_os_error")
            self.assertNotIn("secret request url", raw)

    def test_safe_requests_proxy_error_kind_is_allowlisted(self):
        from scripts.akshare_dual_smoke import _safe_error
        ProxyError = type("ProxyError", (OSError,), {"__module__": "requests.exceptions"})
        category, kind = _safe_error(ProxyError("sensitive proxy address"))
        self.assertEqual(category, "operating_system_or_network")
        self.assertEqual(kind, "proxy")

if __name__ == "__main__":
    unittest.main()
