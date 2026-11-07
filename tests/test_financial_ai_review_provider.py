import unittest
from unittest.mock import Mock

from scripts.financial_ai_review_provider import make_provider_reviewer, review_financial_changes


class FinancialAiReviewProviderTests(unittest.TestCase):
    def test_each_specialist_uses_separate_bound_request(self):
        calls = []
        def invoke(**kwargs):
            calls.append(kwargs)
            return {"status": "ADVISORY_ONLY", "merge_authorized": False,
                    "review": {"verdict": "uncertain", "summary": "Need source evidence.",
                               "findings": []}}
        reviewer = make_provider_reviewer(
            head_sha="a" * 40, endpoint="https://api.example.com/v1/chat/completions",
            token="test-token", model="test-model", allowed_hosts=["api.example.com"],
            invoke=invoke)
        task = {"role": "fundamental", "files": ["scripts/fundamental_metrics.py"],
                "checks": ["check filing timestamp"], "output_requirements": ["cite evidence"],
                "diff_by_file": {"scripts/fundamental_metrics.py": "+ratio = x / y"}}
        result = reviewer(task)
        self.assertEqual(result["verdict"], "uncertain")
        self.assertEqual(len(calls), 1)
        self.assertEqual(calls[0]["expected_head_sha"], "a" * 40)
        payload = calls[0]["prepared"]["request"]["untrusted_pr_data"]
        self.assertIn("fundamental", payload)
        self.assertIn("check filing timestamp", payload)

    def test_runs_independent_provider_calls_for_matching_specialists(self):
        calls = []
        def invoke(**kwargs):
            calls.append(kwargs)
            return {"status": "ADVISORY_ONLY", "merge_authorized": False,
                    "review": {"verdict": "uncertain", "summary": "Insufficient source data.",
                               "findings": []}}
        files = ["scripts/market_data.py", "scripts/fundamental_metrics.py",
                 "scripts/technical_indicators.py", "scripts/backtest_engine.py",
                 "scripts/portfolio_risk.py"]
        diffs = {path: "+placeholder = True" for path in files}
        result = review_financial_changes(
            head_sha="b" * 40, financial_files=files, diff_by_file=diffs,
            endpoint="https://api.example.com/v1/chat/completions",
            token="test-token", model="test-model", allowed_hosts=["api.example.com"],
            invoke=invoke)
        self.assertEqual(len(calls), 5)
        self.assertEqual(len(result["specialist_reviews"]), 5)
        self.assertEqual(result["overall_verdict"], "uncertain")
        self.assertFalse(result["merge_authorized"])

    def test_rejects_missing_allowlist_before_invocation(self):
        with self.assertRaisesRegex(ValueError, "allowlist"):
            make_provider_reviewer(head_sha="a" * 40,
                                   endpoint="https://api.example.com/v1/chat/completions",
                                   token="x", model="m", allowed_hosts=[])

    def test_rejects_inconsistent_task_file_map(self):
        reviewer = make_provider_reviewer(
            head_sha="a" * 40, endpoint="https://api.example.com/v1/chat/completions",
            token="x", model="m", allowed_hosts=["api.example.com"],
            invoke=Mock())
        with self.assertRaisesRegex(ValueError, "diff map"):
            reviewer({"role": "risk", "files": ["scripts/risk.py"],
                      "diff_by_file": {}})


if __name__ == "__main__":
    unittest.main()
