import json
import unittest

from scripts.ai_review_provider_adapter import build_request

SHA = "a" * 40


class FinancialContextAdapterTests(unittest.TestCase):
    def test_financial_context_is_attached_to_review_payload(self):
        context = json.dumps({
            "review_scope": "core_financial_logic_review",
            "required_checks": ["point-in-time"],
            "merge_authorized": False,
        })
        request = build_request(
            head_sha=SHA, changed_files=["scripts/backtest_engine.py"],
            diff="+prices = prices.shift(-1)", financial_context=context)
        payload = json.loads(request["untrusted_pr_data"])
        self.assertEqual(payload["trusted_financial_review_context"]["review_scope"],
                         "core_financial_logic_review")
        self.assertIn("heuristic finding is not a defect", request["system_instructions"])
        self.assertFalse(payload["trusted_financial_review_context"]["merge_authorized"])

    def test_context_is_optional_for_existing_callers(self):
        request = build_request(head_sha=SHA, changed_files=["docs/readme.md"], diff="+text")
        self.assertNotIn("trusted_financial_review_context",
                         json.loads(request["untrusted_pr_data"]))

    def test_rejects_invalid_or_authorizing_context(self):
        for context in ("not json", json.dumps({"merge_authorized": True}), "x" * 12001):
            with self.subTest(context=context), self.assertRaises(ValueError):
                build_request(head_sha=SHA, changed_files=["scripts/market.py"],
                              diff="+x", financial_context=context)

    def test_duplicate_paths_rejected(self):
        with self.assertRaisesRegex(ValueError, "file list"):
            build_request(head_sha=SHA, changed_files=["a.py", "a.py"], diff="+x")


if __name__ == "__main__":
    unittest.main()
