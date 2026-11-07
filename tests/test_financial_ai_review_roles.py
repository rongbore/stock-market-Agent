import unittest

from scripts.financial_ai_review_roles import build_specialist_assignments


class FinancialAiReviewRolesTests(unittest.TestCase):
    def test_routes_financial_paths_to_distinct_roles(self):
        result = build_specialist_assignments([
            "scripts/market_data.py", "scripts/fundamental_metrics.py",
            "scripts/technical_indicators.py", "scripts/backtest_engine.py",
            "scripts/portfolio_risk.py",
        ])
        roles = {item["role"] for item in result}
        self.assertEqual(roles, {"market_data", "fundamental", "technical_indicators",
                                 "quant_backtest", "risk"})
        self.assertTrue(all(item["checks"] for item in result))
        self.assertTrue(all(item["output_requirements"] for item in result))

    def test_only_matching_specialists_are_assigned(self):
        result = build_specialist_assignments(["scripts/backtest_engine.py"])
        self.assertEqual([x["role"] for x in result], ["quant_backtest"])

    def test_empty_and_generic_paths_create_no_specialist_calls(self):
        self.assertEqual(build_specialist_assignments([]), [])
        self.assertEqual(build_specialist_assignments(["docs/readme.md"]), [])

    def test_rejects_invalid_and_duplicate_paths(self):
        for paths in ([None], ["a.py", "a.py"], ["x" * 501], ["a"] * 201):
            with self.subTest(paths=paths), self.assertRaises(ValueError):
                build_specialist_assignments(paths)


if __name__ == "__main__":
    unittest.main()
