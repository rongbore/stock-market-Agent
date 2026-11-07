import unittest
from scripts.market_research_brief import build_brief, render_markdown


class MarketResearchBriefTests(unittest.TestCase):
    def report(self):
        return {"symbol": "000776.SZ", "dates": ["2026-10-01", "2026-10-02"],
                "prices": [10, 11], "numerical_agreement": False}

    def test_evidence_based_not_directional_recommendation(self):
        brief = build_brief(self.report())
        self.assertEqual(brief["historical_direction"], "上涨")
        self.assertIn("证据不足", brief["research_stance"])
        self.assertFalse(brief["is_trading_advice"])
        self.assertLessEqual(len(brief["facts"]), 5)

    def test_no_fabricated_fundamental_claim(self):
        brief = build_brief(self.report())
        self.assertIn("已核验的公司财报", brief["missing_evidence"])
        self.assertIn("财报", render_markdown(brief))

    def test_single_day_insufficient_for_change(self):
        r = self.report()
        r["dates"], r["prices"] = r["dates"][:1], r["prices"][:1]
        self.assertEqual(build_brief(r)["historical_direction"], "无法判断")

    def test_invalid_data_rejected(self):
        r = self.report()
        r["prices"] = [10, float("inf")]
        with self.assertRaisesRegex(ValueError, "invalid price"):
            build_brief(r)

    def test_unaligned_dates_rejected(self):
        r = self.report()
        r["dates"] = ["2026-10-01"]
        with self.assertRaisesRegex(ValueError, "unaligned"):
            build_brief(r)


if __name__ == "__main__":
    unittest.main()
