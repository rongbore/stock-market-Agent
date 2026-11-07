import unittest
from scripts.market_trend_report import build_report


def snap(upstream, close):
    return {"symbol": "000776.SZ", "adjust": "qfq", "price_unit": "CNY_per_share",
            "upstream": upstream, "records": [{"date": "2026-10-01", "close": close}]}


class MarketTrendDivergenceTests(unittest.TestCase):
    def test_divergence_rejected_without_comparison(self):
        with self.assertRaisesRegex(ValueError, "divergence"):
            build_report(snap("eastmoney", 10), snap("sina", 12))

    def test_forged_pass_does_not_override_price_divergence(self):
        with self.assertRaisesRegex(ValueError, "divergence"):
            build_report(snap("eastmoney", 10), snap("sina", 12),
                         {"status": "passed", "cross_source_numerical_agreement": True})

    def test_failed_comparison_blocks_chart(self):
        with self.assertRaisesRegex(ValueError, "not passed"):
            build_report(snap("eastmoney", 10), snap("sina", 10),
                         {"status": "failed", "cross_source_numerical_agreement": False})

    def test_comparison_symbol_mismatch_rejected(self):
        with self.assertRaisesRegex(ValueError, "comparison symbol mismatch"):
            build_report(snap("eastmoney", 10), snap("sina", 10),
                         {"status": "passed", "cross_source_numerical_agreement": True,
                          "symbol": "000001.SZ"})

    def test_agreeing_prices_remain_available(self):
        report = build_report(snap("eastmoney", 10), snap("sina", 10.01))
        self.assertEqual(report["shared_points"], 1)
        self.assertFalse(report["numerical_agreement"])


if __name__ == "__main__":
    unittest.main()
