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


if __name__ == "__main__":
    unittest.main()
