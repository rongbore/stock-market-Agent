import unittest
from unittest.mock import patch

from scripts import ai_review_manual_cli as cli

SHA = "a" * 40


def pr(sha=SHA):
    return {"state": "open", "base": {"ref": "main"}, "head": {"sha": sha}}


class ManualReviewCliTests(unittest.TestCase):
    def test_success_fetches_pr_diff_and_returns_advisory_only(self):
        calls = []
        def github(path, token):
            calls.append(path)
            if path.endswith("/files?per_page=100&page=1"):
                return [{"filename": "docs/a.md", "status": "modified", "patch": "@@ -1 +1 @@\n-a\n+b"}]
            return pr()
        model = {"review": {"verdict": "approve", "findings": [], "summary": "ok"}}
        with patch.object(cli, "github_json", side_effect=github), patch.object(cli, "prepare_review", return_value={"request_digest": "d"}), patch.object(cli, "invoke_review", return_value=model):
            result = cli.run(repo="rongbore/stock-market-Agent", pr_number=1, github_token="gh", model_token="ai", endpoint="https://api.example.com/v1/chat/completions", model="m")
        self.assertFalse(result["merge_authorized"])
        self.assertTrue(any("/files?" in x for x in calls))

    def test_closed_pr_rejected(self):
        with patch.object(cli, "github_json", return_value={"state": "closed", "base": {"ref": "main"}, "head": {"sha": SHA}}):
            with self.assertRaisesRegex(ValueError, "not open"):
                cli.run(repo="rongbore/stock-market-Agent", pr_number=1, github_token="gh", model_token="ai", endpoint="https://api.example.com", model="m")

    def test_wrong_base_rejected(self):
        with patch.object(cli, "github_json", return_value={"state": "open", "base": {"ref": "dev"}, "head": {"sha": SHA}}):
            with self.assertRaisesRegex(ValueError, "not open"):
                cli.run(repo="rongbore/stock-market-Agent", pr_number=1, github_token="gh", model_token="ai", endpoint="https://api.example.com", model="m")

    def test_missing_patch_rejected(self):
        def github(path, token):
            if "/files?" in path:
                return [{"filename": "file.bin", "status": "modified"}]
            return pr()
        with patch.object(cli, "github_json", side_effect=github):
            with self.assertRaisesRegex(ValueError, "patch"):
                cli.run(repo="rongbore/stock-market-Agent", pr_number=1, github_token="gh", model_token="ai", endpoint="https://api.example.com", model="m")

    def test_pr_sha_change_during_review_rejected(self):
        n = 0
        def github(path, token):
            nonlocal n
            if "/files?" in path:
                return [{"filename": "docs/a.md", "status": "modified", "patch": "+a"}]
            n += 1
            return pr(SHA if n == 1 else "b" * 40)
        with patch.object(cli, "github_json", side_effect=github), patch.object(cli, "prepare_review", return_value={"request_digest": "d"}), patch.object(cli, "invoke_review", return_value={"review": {"verdict": "approve", "findings": [], "summary": "ok"}}):
            with self.assertRaisesRegex(ValueError, "changed"):
                cli.run(repo="rongbore/stock-market-Agent", pr_number=1, github_token="gh", model_token="ai", endpoint="https://api.example.com", model="m")


if __name__ == "__main__":
    unittest.main()
