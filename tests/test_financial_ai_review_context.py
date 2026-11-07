import json
import unittest

from scripts.financial_ai_review_context import build_financial_review_context
from scripts.financial_ai_review_rules import assess_financial_pr


class FinancialAiReviewContextTests(unittest.TestCase):
    def test_core_scope_generates_evidence_first_checks(self):
        preflight = assess_financial_pr(
            ["scripts/backtest_engine.py"],
            {"scripts/backtest_engine.py": "prices = prices.shift(-1)"})
        payload = json.loads(build_financial_review_context(preflight))
        self.assertEqual(payload["review_scope"], "core_financial_logic_review")
        self.assertFalse(payload["merge_authorized"])
        self.assertFalse(payload["investment_advice"])
        self.assertTrue(any("point-in-time" in x for x in payload["review_protocol"]))
        self.assertTrue(payload["heuristic_findings"])
        self.assertEqual(payload["specialist_assignments"][0]["role"], "quant_backtest")

    def test_general_scope_is_still_valid(self):
        preflight = assess_financial_pr(["docs/usage.md"])
        payload = json.loads(build_financial_review_context(preflight))
        self.assertEqual(payload["review_scope"], "general_review")

    def test_rejects_non_advisory_or_unknown_scope(self):
        preflight = assess_financial_pr(["scripts/market_data.py"])
        with self.assertRaisesRegex(ValueError, "advisory-only"):
            build_financial_review_context(dict(preflight, merge_authorized=True))
        with self.assertRaisesRegex(ValueError, "scope"):
            build_financial_review_context(dict(preflight, scope="auto_trade"))

    def test_context_is_bounded(self):
        preflight = assess_financial_pr(["scripts/market_data.py"])
        huge = dict(preflight, required_review_checks=["x" * 1000] * 200)
        with self.assertRaisesRegex(ValueError, "size limit"):
            build_financial_review_context(huge)


if __name__ == "__main__":
    unittest.main()
