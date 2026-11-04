import unittest
from scripts.akshare_crosscheck import compare


def snapshot(upstream="eastmoney", unit="lots_100_shares", volume=432885):
    return {
        "symbol": "000776.SZ", "upstream": upstream, "adjust": "",
        "start_date": "2026-10-01", "end_date": "2026-10-30",
        "volume_unit": unit,
        "records": [{"date": "2026-10-08", "open": 19.8, "high": 19.98,
                     "low": 19.21, "close": 19.32, "volume": volume}],
    }


class CrosscheckTests(unittest.TestCase):
    def test_distinct_upstreams_and_normalized_volume_pass(self):
        result = compare(snapshot(), snapshot("other-provider", "shares", 43288500))
        self.assertEqual(result["status"], "passed")
        self.assertTrue(result["independent_source_verified"])

    def test_same_upstream_does_not_verify(self):
        result = compare(snapshot(), snapshot())
        self.assertEqual(result["status"], "failed")
        self.assertFalse(result["independent_upstream"])

    def test_price_mismatch_detected(self):
        other = snapshot("other-provider")
        other["records"][0]["close"] = 19.5
        result = compare(snapshot(), other)
        self.assertEqual(result["difference_count"], 1)
        self.assertEqual(result["differences"][0]["field"], "close")

    def test_missing_date_detected(self):
        other = snapshot("other-provider")
        other["records"][0]["date"] = "2026-10-09"
        self.assertEqual(compare(snapshot(), other)["difference_count"], 2)

    def test_missing_volume_units_rejected(self):
        other = snapshot("other-provider")
        del other["volume_unit"]
        with self.assertRaises(ValueError):
            compare(snapshot(), other)


if __name__ == "__main__":
    unittest.main()
