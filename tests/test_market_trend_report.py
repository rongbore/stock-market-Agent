import unittest
from scripts.market_trend_report import build_report, render_html, render_markdown


def snap(upstream, dates, prices):
    return {
        "symbol": "000776.SZ", "adjust": "qfq", "price_unit": "CNY_per_share",
        "upstream": upstream,
        "records": [{"date": d, "close": p} for d, p in zip(dates, prices)],
    }


class MarketTrendReportTests(unittest.TestCase):
    def setUp(self):
        self.a = snap("eastmoney", ["2026-10-01", "2026-10-02", "2026-10-05", "2026-10-06", "2026-10-07"], [10, 10.2, 10.1, 10.5, 10.8])
        self.b = snap("sina", ["2026-10-01", "2026-10-02", "2026-10-05", "2026-10-06", "2026-10-07"], [10.01, 10.19, 10.11, 10.49, 10.81])

    def test_sorted_shared_dates_and_trend_metrics(self):
        self.a["records"].reverse()
        report = build_report(self.a, self.b, {"status": "passed", "cross_source_numerical_agreement": True, "independent_source_verified": False})
        self.assertEqual(report["dates"][0], "2026-10-01")
        self.assertEqual(report["shared_points"], 5)
        self.assertGreater(report["change_pct"], 0)
        self.assertTrue(report["numerical_agreement"])
        self.assertFalse(report["source_verified"])

    def test_missing_dates_are_not_filled(self):
        self.b["records"].pop(2)
        report = build_report(self.a, self.b)
        self.assertEqual(report["shared_points"], 4)
        self.assertNotIn("2026-10-05", report["dates"])

    def test_empty_shared_dates_rejected(self):
        self.b["records"] = [{"date": "2026-11-01", "close": 10}]
        with self.assertRaisesRegex(ValueError, "no shared dates"):
            build_report(self.a, self.b)

    def test_bad_values_and_adjustment_mismatch_rejected(self):
        self.a["records"][0]["close"] = float("nan")
        with self.assertRaisesRegex(ValueError, "invalid close"):
            build_report(self.a, self.b)
        self.a["records"][0]["close"] = 10
        self.b["adjust"] = ""
        with self.assertRaisesRegex(ValueError, "mismatch"):
            build_report(self.a, self.b)

    def test_html_and_markdown_escape_and_show_data_boundary(self):
        self.a["symbol"] = "<script>alert(1)</script>"
        self.b["symbol"] = self.a["symbol"]
        report = build_report(self.a, self.b)
        html = render_html(report)
        md = render_markdown(report)
        self.assertNotIn("<script>", html)
        self.assertIn("&lt;script&gt;", html)
        self.assertIn("不代表交易所认证", html)
        self.assertIn("数据边界", md)
        self.assertIn("| 日期 |", md)

    def test_insufficient_points_do_not_claim_direction(self):
        a = snap("eastmoney", ["2026-10-01"], [10])
        b = snap("sina", ["2026-10-01"], [10])
        report = build_report(a, b)
        self.assertEqual(report["trend"], "数据不足，暂不判断")
        self.assertIsNone(report["change_pct"])


if __name__ == "__main__":
    unittest.main()
