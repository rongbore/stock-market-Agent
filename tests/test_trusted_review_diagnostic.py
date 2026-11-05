import unittest
from unittest.mock import patch

from scripts import trusted_review_diagnostic as diagnostic


class DiagnosticTests(unittest.TestCase):
    def setUp(self):
        self.sha = "a" * 40
        self.pr = {"state": "open", "changed_files": 1, "head": {"sha": self.sha},
                   "user": {"login": "alice"}}
        self.files = [{"filename": "scripts/app.py", "status": "modified",
                       "additions": 1, "deletions": 0}]
        self.reviews = [{"user": {"login": "bob"}, "state": "APPROVED",
                         "submitted_at": "2026-11-04T08:00:00Z",
                         "commit_id": self.sha}]

    def fake_api(self, path):
        if "/collaborators/" in path:
            return {"permission": "write"}
        return self.pr

    def fake_pages(self, path):
        return self.files if "/files?" in path else self.reviews

    def test_approved_current_head(self):
        with patch.object(diagnostic, "api", side_effect=self.fake_api), patch.object(
            diagnostic, "api_paginated", side_effect=self.fake_pages
        ):
            self.assertTrue(diagnostic.run("owner/repo", 1)[0])

    def test_changed_head_blocks(self):
        calls = iter([self.pr, {**self.pr, "head": {"sha": "b" * 40}}])
        def changed(path):
            if "/collaborators/" in path:
                return {"permission": "write"}
            return next(calls)
        with patch.object(diagnostic, "api", side_effect=changed), patch.object(
            diagnostic, "api_paginated", side_effect=self.fake_pages
        ):
            self.assertFalse(diagnostic.run("owner/repo", 1)[0])

    def test_missing_permission_blocks(self):
        def no_permission(path):
            if "/collaborators/" in path:
                return {"permission": "read"}
            return self.pr
        with patch.object(diagnostic, "api", side_effect=no_permission), patch.object(
            diagnostic, "api_paginated", side_effect=self.fake_pages
        ):
            self.assertFalse(diagnostic.run("owner/repo", 1)[0])

    def test_null_reviewer_does_not_crash(self):
        self.reviews[0]["user"] = None
        with patch.object(diagnostic, "api", side_effect=self.fake_api), patch.object(
            diagnostic, "api_paginated", side_effect=self.fake_pages
        ):
            self.assertFalse(diagnostic.run("owner/repo", 1)[0])


if __name__ == "__main__":
    unittest.main()
