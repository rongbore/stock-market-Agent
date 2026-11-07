import unittest

from scripts.financial_ai_review_rules import assess_financial_pr


class FinancialAiReviewRulesTests(unittest.TestCase):
    def test_core_financial_paths_get_strict_scope(self):
        result = assess_financial_pr(
            ["scripts/backtest_engine.py", "tests/test_backtest_engine.py"],
            {"scripts/backtest_engine.py": "run_backtest(data)"})
        self.assertEqual(result["scope"], "core_financial_logic_review")
        self.assertFalse(result["merge_authorized"])
        self.assertTrue(result["ai_review_is_advisory"])
        self.assertIn("回测是否避免未来函数", result["required_review_checks"][4])

    def test_future_data_and_silent_zero_fill_are_flagged(self):
        result = assess_financial_pr(
            ["scripts/market_data.py"],
            {"scripts/market_data.py": "prices = prices.shift(-1)\nprices = prices.fillna(0)"})
        codes = {item["code"] for item in result["findings"]}
        self.assertIn("future_data_access", codes)
        self.assertIn("silent_missing_value_fill", codes)

    def test_sensitive_workflow_change_gets_restricted_scope(self):
        result = assess_financial_pr([".github/workflows/market.yml"])
        self.assertEqual(result["scope"], "restricted_security_review")
        self.assertTrue(result["sensitive_files"])

    def test_generic_docs_remain_general_review(self):
        result = assess_financial_pr(["docs/usage.md"])
        self.assertEqual(result["scope"], "general_review")
        self.assertEqual(result["required_review_checks"], [])

    def test_unadjusted_and_adjusted_price_mix_is_flagged(self):
        result = assess_financial_pr(
            ["scripts/market_indicators.py"],
            {"scripts/market_indicators.py": "close = qfq_close / raw_close"})
        self.assertIn("unadjusted_price_mix", {x["code"] for x in result["findings"]})

    def test_unsafe_duplicate_and_unknown_diff_paths_rejected(self):
        for paths, diffs in (
            (["../secrets.txt"], {}),
            (["a.py", "a.py"], {}),
            (["a.py"], {"b.py": "diff"}),
        ):
            with self.subTest(paths=paths, diffs=diffs), self.assertRaises(ValueError):
                assess_financial_pr(paths, diffs)

    def test_bounds_are_enforced(self):
        with self.assertRaises(ValueError):
            assess_financial_pr(["a.py"] * 201)
        with self.assertRaises(ValueError):
            assess_financial_pr(["scripts/market.py"], {"scripts/market.py": "x" * 500_001})


if __name__ == "__main__":
    unittest.main()
