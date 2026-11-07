import unittest
from unittest.mock import patch

from scripts.ai_review_manual_cli import run

REPO = "rongbore/stock-market-Agent"
SHA = "a" * 40


class ManualCliRoundtableTests(unittest.TestCase):
    def _pr(self):
        return {
            "state": "open",
            "base": {"repo": {"full_name": REPO}},
            "head": {"repo": {"full_name": REPO}, "sha": SHA},
        }

    def _roundtable(self):
        return {
            "overall_verdict": "uncertain",
            "independent_reviews": [{"findings": []}],
            "discussion_transcript": [],
            "specialist_final_positions": [],
            "moderator_synthesis": {
                "verdict": "approve",
                "summary": "Evidence remains incomplete.",
                "findings": [],
            },
            "merge_authorized": False,
            "review_advisory_only": True,
        }

    @patch("scripts.ai_review_manual_cli.review_financial_changes_with_roundtable")
    @patch("scripts.ai_review_manual_cli.github_json")
    def test_financial_pr_uses_roundtable_and_reports_call_count(self, github, roundtable):
        github.side_effect = [
            self._pr(),
            [{"filename": "scripts/backtest_engine.py",
              "status": "modified", "patch": "@@ -1 +1 @@\n+run_backtest()"}],
            self._pr(),
        ]
        roundtable.return_value = self._roundtable()
        result = run(
            repo=REPO, pr_number=7, github_token="gh-test",
            model_token="model-test", endpoint="https://api.example.com/v1/chat/completions",
            model="test-model",
        )
        roundtable.assert_called_once()
        self.assertEqual(roundtable.call_args.kwargs["financial_files"],
                         ["scripts/backtest_engine.py"])
        self.assertEqual(result["verdict"], "uncertain")
        self.assertEqual(result["model_calls"], 16)
        self.assertFalse(result["merge_authorized"])

    @patch("scripts.ai_review_manual_cli.review_financial_changes_with_roundtable")
    @patch("scripts.ai_review_manual_cli.invoke_review")
    @patch("scripts.ai_review_manual_cli.github_json")
    def test_sensitive_financial_pr_keeps_single_review_path(
        self, github, invoke, roundtable
    ):
        github.side_effect = [
            self._pr(),
            [{"filename": "scripts/financial_broker_auth.py",
              "status": "modified", "patch": "@@ -1 +1 @@\n+auth_change = True"}],
            self._pr(),
        ]
        invoke.return_value = {
            "review": {"verdict": "uncertain", "summary": "Requires trusted review.",
                       "findings": []}
        }
        result = run(
            repo=REPO, pr_number=8, github_token="gh-test",
            model_token="model-test", endpoint="https://api.example.com/v1/chat/completions",
            model="test-model",
        )
        roundtable.assert_not_called()
        invoke.assert_called_once()
        self.assertEqual(result["model_calls"], 1)
        self.assertEqual(result["verdict"], "uncertain")
        self.assertFalse(result["merge_authorized"])

    @patch("scripts.ai_review_manual_cli.review_financial_changes_with_roundtable")
    @patch("scripts.ai_review_manual_cli.invoke_review")
    @patch("scripts.ai_review_manual_cli.github_json")
    def test_mixed_pr_reviews_nonfinancial_files_too(
        self, github, invoke, roundtable
    ):
        github.side_effect = [
            self._pr(),
            [
                {"filename": "scripts/backtest_engine.py",
                 "status": "modified", "patch": "@@ -1 +1 @@\n+run_backtest()"},
                {"filename": "docs/readme.md",
                 "status": "modified", "patch": "@@ -1 +1 @@\n+documentation"},
            ],
            self._pr(),
        ]
        roundtable.return_value = self._roundtable()
        invoke.return_value = {
            "review": {"verdict": "approve", "summary": "Docs reviewed.",
                       "findings": []}
        }
        result = run(
            repo=REPO, pr_number=9, github_token="gh-test",
            model_token="model-test", endpoint="https://api.example.com/v1/chat/completions",
            model="test-model",
        )
        roundtable.assert_called_once()
        invoke.assert_called_once()
        self.assertEqual(result["model_calls"], 17)
        self.assertEqual(result["verdict"], "uncertain")
        self.assertIn("非金融文件审核", result["summary"])


if __name__ == "__main__":
    unittest.main()
