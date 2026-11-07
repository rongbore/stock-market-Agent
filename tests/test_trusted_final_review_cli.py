import contextlib
import io
import json
import os
import tempfile
import unittest
from unittest.mock import patch

from scripts.trusted_final_review_cli import main
from scripts.final_review_gate import REQUIRED_CHECKS

PR_ARGS = ["--repo", "owner/repo", "--pr-number", "7", "--head-sha", SHA]

SHA = "a" * 40


class TrustedFinalReviewCliTests(unittest.TestCase):
    def test_missing_token_blocks_without_leak(self):
        with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", delete=True) as f:
            json.dump({"head_sha": SHA}, f)
            f.flush()
            output = io.StringIO()
            with patch.dict(os.environ, {"GITHUB_TOKEN": ""}), contextlib.redirect_stdout(output):
                code = main(PR_ARGS + ["--evidence-json", f.name])
            self.assertEqual(code, 1)
            self.assertEqual(json.loads(output.getvalue())["decision"], "BLOCKED")

    @patch("scripts.trusted_final_review_cli.fetch_pr_metadata")
    @patch("scripts.trusted_final_review_cli.fetch_workflow_runs")
    def test_valid_live_runs_still_never_authorize_merge(self, fetch, fetch_pr):
        fetch_pr.return_value = {"head_sha": SHA, "is_draft": False,
                                 "changed_paths": ["docs/guide.md"],
                                 "pr_number": 7, "base_repo": "owner/repo",
                                 "merge_authorized": False}
        fetch.return_value = [
            {"id": i + 1, "name": name, "head_sha": SHA, "event": "pull_request",
             "status": "completed", "conclusion": "success"}
            for i, name in enumerate(sorted(REQUIRED_CHECKS))
        ]
        evidence = {"head_sha": SHA, "risk": {"status": "CANDIDATE", "head_sha": SHA},
                    "ai_review": {"verdict": "PASS", "head_sha": SHA, "review_complete": True,
                                  "findings": [], "policy_version": "1"},
                    "is_draft": False, "changed_paths": ["docs/guide.md"]}
        with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", delete=True) as f:
            json.dump(evidence, f)
            f.flush()
            output = io.StringIO()
            with contextlib.redirect_stdout(output):
                code = main(["--repo", "owner/repo", "--head-sha", SHA, "--evidence-json", f.name])
            result = json.loads(output.getvalue())
            self.assertEqual(code, 0)
            self.assertEqual(result["decision"], "ELIGIBLE_FOR_POLICY_REVIEW")
            self.assertFalse(result["merge_authorized"])
            self.assertEqual(fetch_pr.call_count, 2)

    @patch("scripts.trusted_final_review_cli.fetch_pr_metadata")
    @patch("scripts.trusted_final_review_cli.fetch_workflow_runs")
    def test_pr_changed_during_review_blocks(self, fetch, fetch_pr):
        fetch.return_value = [
            {"id": i + 1, "name": name, "head_sha": SHA,
             "event": "pull_request", "status": "completed", "conclusion": "success"}
            for i, name in enumerate(sorted(REQUIRED_CHECKS))
        ]
        base = {"head_sha": SHA, "is_draft": False,
                "changed_paths": ["docs/guide.md"], "pr_number": 7,
                "base_repo": "owner/repo", "merge_authorized": False}
        fetch_pr.side_effect = [base, {**base, "is_draft": True}]
        evidence = {"head_sha": SHA, "risk": {"status": "CANDIDATE", "head_sha": SHA},
                    "ai_review": {"verdict": "PASS", "head_sha": SHA,
                                  "review_complete": True, "findings": [],
                                  "policy_version": "1"}}
        with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", delete=True) as f:
            json.dump(evidence, f)
            f.flush()
            output = io.StringIO()
            with contextlib.redirect_stdout(output):
                code = main(PR_ARGS + ["--evidence-json", f.name])
            self.assertEqual(code, 1)
            self.assertEqual(json.loads(output.getvalue())["decision"], "BLOCKED")


if __name__ == "__main__":
    unittest.main()
