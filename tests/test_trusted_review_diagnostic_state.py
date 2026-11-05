import unittest
from unittest.mock import patch

from scripts.trusted_review_diagnostic import run


class TrustedDiagnosticStateTests(unittest.TestCase):
    @patch("scripts.trusted_review_diagnostic.api")
    def test_closed_pr_does_not_fetch_review_data(self, api):
        api.return_value = {"state": "closed"}
        allowed, reason = run("owner/repo", 42)
        self.assertFalse(allowed)
        self.assertIn("not open", reason)
        api.assert_called_once()

    @patch("scripts.trusted_review_diagnostic.check", return_value=(True, "approved"))
    @patch("scripts.trusted_review_diagnostic.api_paginated")
    @patch("scripts.trusted_review_diagnostic.api")
    def test_closure_during_verification_blocks(self, api, pages, check):
        sha = "a" * 40
        api.side_effect = [
            {"state": "open", "changed_files": 1, "head": {"sha": sha},
             "user": {"login": "alice"}},
            {"state": "closed", "head": {"sha": sha}},
        ]
        pages.side_effect = [[{"filename": "docs/readme.md"}], []]
        allowed, reason = run("owner/repo", 42)
        self.assertFalse(allowed)
        self.assertIn("closed", reason)


if __name__ == "__main__":
    unittest.main()
