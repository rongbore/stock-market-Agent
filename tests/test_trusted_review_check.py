import unittest
from scripts.trusted_review_check import check


class TrustedReviewCheckTests(unittest.TestCase):
    def setUp(self):
        self.sha = "a" * 40
        self.pr = {"changed_files": 1, "head_sha": self.sha, "author": "alice"}
        self.code = [{"filename": "scripts/app.py", "status": "modified", "additions": 1, "deletions": 0}]
        self.docs = [{"filename": "docs/readme.md", "status": "modified", "additions": 1, "deletions": 0}]
        self.approval = {"user": "bob", "state": "APPROVED", "commit_id": self.sha,
                         "submitted_at": "2026-11-04T08:00:00Z"}

    def test_docs_pass(self):
        self.assertTrue(check(self.pr, self.docs, [], [])[0])

    def test_sensitive_requires_trusted_review(self):
        self.assertFalse(check(self.pr, self.code, [], [])[0])
        self.assertFalse(check(self.pr, self.code, [self.approval], [])[0])
        self.assertTrue(check(self.pr, self.code, [self.approval], ["bob"])[0])
        self.assertFalse(check(self.pr, self.code, [{**self.approval, "commit_id": "b" * 40}], ["bob"])[0])
        self.assertFalse(check(self.pr, self.code, [{**self.approval, "user": "alice"}], ["alice"])[0])

    def test_change_request_blocks(self):
        reviews = [self.approval, {"user": "carol", "state": "CHANGES_REQUESTED",
                                 "commit_id": self.sha, "submitted_at": "2026-11-04T08:01:00Z"}]
        self.assertFalse(check(self.pr, self.code, reviews, ["bob"])[0])

    def test_review_timestamp_timezone_order(self):
        old_request = {"user": "bob", "state": "CHANGES_REQUESTED",
                       "commit_id": self.sha, "submitted_at": "2026-11-04T10:00:00+03:00"}
        self.assertTrue(check(self.pr, self.code, [old_request, self.approval], ["bob"])[0])
        self.assertFalse(check(self.pr, self.code, [{**self.approval, "submitted_at": "invalid"}], ["bob"])[0])

    def test_incomplete_data_blocks(self):
        self.assertFalse(check({**self.pr, "changed_files": 2}, self.docs, [], [])[0])
        self.assertFalse(check({**self.pr, "head_sha": ""}, self.docs, [], [])[0])


if __name__ == "__main__":
    unittest.main()
