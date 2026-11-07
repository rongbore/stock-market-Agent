import unittest
from scripts.market_trend_report import build_report, render_html, render_markdown


def snapshot(upstream, n):
    return {
        "symbol": "000776.SZ", "adjust": "qfq", "price_unit": "CNY_per_share",
        "upstream": upstream,
        "records": [{"date": f"2026-10-{i+1:02d}", "close": 10 + i / 10}
                    for i in range(n)],
    }


class MarketTrendIntegrationTests(unittest.TestCase):
    def test_html_has_three_lines(self):
        report = build_report(snapshot("eastmoney", 20), snapshot("sina", 20))
        html = render_html(report)
        self.assertIn('data-series="Close"', html)
        self.assertIn('data-series="MA5"', html)
        self.assertIn('data-series="MA20"', html)
        self.assertIn("不构成交易信号", html)

    def test_markdown_has_moving_average_table(self):
        report = build_report(snapshot("eastmoney", 20), snapshot("sina", 20))
        md = render_markdown(report)
        self.assertIn("## MA5 / MA20 历史均线", md)
        self.assertIn("MA5高于MA20", md)
        self.assertIn("2026-10-20", md)

    def test_short_history_does_not_invent_values(self):
        report = build_report(snapshot("eastmoney", 3), snapshot("sina", 3))
        html = render_html(report)
        md = render_markdown(report)
        self.assertNotIn('data-series="MA5"', html)
        self.assertNotIn('data-series="MA20"', html)
        self.assertIn("数据不足", md)


if __name__ == "__main__":
    unittest.main()
