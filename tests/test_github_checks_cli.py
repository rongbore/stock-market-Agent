import contextlib
import io
import json
import os
import unittest
from unittest.mock import patch

from scripts.github_checks_cli import main
from scripts.final_review_gate import REQUIRED_CHECKS

SHA = "a" * 40


class GithubChecksCliTests(unittest.TestCase):
    def test_missing_token_fails_closed_without_leaking(self):
        output = io.StringIO()
        with patch.dict(os.environ, {"GITHUB_TOKEN": ""}), contextlib.redirect_stdout(output):
            status = main(["--repo", "owner/repo", "--head-sha", SHA])
        self.assertEqual(status, 1)
        self.assertEqual(json.loads(output.getvalue())["status"], "BLOCKED")

    @patch("scripts.github_checks_cli.fetch_workflow_evidence")
    def test_success_remains_non_authorizing(self, fetch):
        fetch.return_value = [
            {"name": name, "head_sha": SHA, "status": "completed",
             "conclusion": "success"} for name in sorted(REQUIRED_CHECKS)
        ]
        output = io.StringIO()
        with patch.dict(os.environ, {"GITHUB_TOKEN": "test-secret"}), contextlib.redirect_stdout(output):
            status = main(["--repo", "owner/repo", "--head-sha", SHA])
        result = json.loads(output.getvalue())
        self.assertEqual(status, 0)
        self.assertFalse(result["merge_authorized"])
        self.assertNotIn("test-secret", output.getvalue())

    @patch("scripts.github_checks_cli.fetch_workflow_evidence", side_effect=ValueError("secret"))
    def test_errors_do_not_expose_exception(self, fetch):
        output = io.StringIO()
        with patch.dict(os.environ, {"GITHUB_TOKEN": "test-secret"}), contextlib.redirect_stdout(output):
            self.assertEqual(main(["--repo", "owner/repo", "--head-sha", SHA]), 1)
        self.assertNotIn("secret", output.getvalue())


if __name__ == "__main__":
    unittest.main()
