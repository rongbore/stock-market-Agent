import unittest
from unittest.mock import patch

from scripts import ai_review_manual_cli as cli

SHA = "a" * 40
REPO = "rongbore/stock-market-Agent"

def make_pr(base="feature-parent", state="open", head_repo=REPO, base_repo=REPO):
    return {"state": state, "base": {"ref": base, "repo": {"full_name": base_repo}},
            "head": {"sha": SHA, "repo": {"full_name": head_repo}}}

class StackedPrTargetTests(unittest.TestCase):
    def run_cli(self, pr):
        def github(path, token):
            if path.endswith("/pulls/42"):
                return pr
            if "/files?" in path:
                return [{"filename":"docs/a.md","status":"modified","patch":"@@ -1 +1 @@\n-a\n+b"}]
            return pr
        fake_result={"review":{"verdict":"approve","findings":[],"summary":"ok"}}
        with patch.object(cli,"github_json",side_effect=github), \
             patch.object(cli,"prepare_review",return_value={"request_digest":"digest"}), \
             patch.object(cli,"invoke_review",return_value=fake_result):
            return cli.run(repo=REPO,pr_number=42,github_token="gh",model_token="model",
                           endpoint="https://api.deepseek.com/chat/completions",model="deepseek-flash")

    def test_stacked_pr_targeting_feature_branch_is_reviewable(self):
        result=self.run_cli(make_pr(base="feat/parent"))
        self.assertTrue(result["review_advisory_only"])
        self.assertFalse(result["merge_authorized"])

    def test_main_target_pr_remains_reviewable(self):
        result=self.run_cli(make_pr(base="main"))
        self.assertFalse(result["merge_authorized"])

    def test_fork_pr_is_rejected(self):
        with self.assertRaisesRegex(ValueError,"trusted repository"):
            self.run_cli(make_pr(head_repo="contributor/fork"))

    def test_closed_pr_is_rejected(self):
        with self.assertRaisesRegex(ValueError,"not open"):
            self.run_cli(make_pr(state="closed"))

if __name__ == "__main__":
    unittest.main()
