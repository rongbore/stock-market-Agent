import unittest
from scripts.trend_chart_overlay import overlay_svg, render_overlay_section


class TrendChartOverlayTests(unittest.TestCase):
    def report(self, n):
        return {"symbol": "000776.SZ", "dates": [f"2026-10-{i+1:02d}" for i in range(n)],
                "prices": [10 + i / 10 for i in range(n)]}

    def test_short_history_shows_close_only(self):
        svg = overlay_svg(self.report(4))
        self.assertIn('data-series="Close"', svg)
        self.assertNotIn('data-series="MA5"', svg)
        self.assertNotIn('data-series="MA20"', svg)

    def test_ma5_without_ma20(self):
        svg = overlay_svg(self.report(10))
        self.assertIn('data-series="MA5"', svg)
        self.assertNotIn('data-series="MA20"', svg)

    def test_full_overlay(self):
        svg = overlay_svg(self.report(20))
        self.assertIn('data-series="MA5"', svg)
        self.assertIn('data-series="MA20"', svg)
        self.assertIn("2026-10-20", svg)

    def test_untrusted_symbol_is_escaped(self):
        report = self.report(20)
        report["symbol"] = "<script>"
        self.assertNotIn("<script>", overlay_svg(report))
        self.assertIn("&lt;script&gt;", overlay_svg(report))

    def test_section_preserves_non_authoritative_boundary(self):
        self.assertIn("不构成交易信号", render_overlay_section(self.report(20)))


if __name__ == "__main__":
    unittest.main()
