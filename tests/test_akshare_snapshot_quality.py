import unittest

from scripts.akshare_snapshot_quality import check_snapshot


def sample():
    return {
        "symbol": "000776.SZ", "source": "akshare",
        "interface": "stock_zh_a_hist", "adjust": "",
        "start_date": "2026-10-01", "end_date": "2026-10-30",
        "source_content_verified": False,
        "historical_point_in_time_verified": False,
        "records": [{"date": "2026-10-08", "open": 19.8, "high": 19.98,
                     "low": 19.21, "close": 19.32, "volume": 432885.0}],
    }


class SnapshotQualityTests(unittest.TestCase):
    def test_valid_snapshot_passes_but_not_independently_verified(self):
        report = check_snapshot(sample())
        self.assertEqual(report["status"], "passed")
        self.assertEqual(report["volume_unit"], "lots_100_shares")
        self.assertFalse(report["independent_source_verified"])

    def test_duplicate_dates_fail(self):
        payload = sample()
        payload["records"].append(dict(payload["records"][0]))
        self.assertEqual(check_snapshot(payload)["status"], "failed")

    def test_invalid_ohlc_fails(self):
        payload = sample()
        payload["records"][0]["low"] = 20
        self.assertEqual(check_snapshot(payload)["status"], "failed")

    def test_invalid_verification_claim_fails(self):
        payload = sample()
        payload["source_content_verified"] = True
        self.assertEqual(check_snapshot(payload)["status"], "failed")

    def test_empty_records_fail(self):
        payload = sample()
        payload["records"] = []
        self.assertEqual(check_snapshot(payload)["status"], "failed")


if __name__ == "__main__":
    unittest.main()
