import unittest
from scripts.risk_approval_gate import evaluate


class RiskApprovalGateTests(unittest.TestCase):
    def setUp(self):
        self.pr = {"changed_files": 1, "user": "author",
                   "pushed_at": "2026-11-04T07:00:00Z"}
        self.doc = [{"filename": "docs/guide.md", "status": "modified",
                     "additions": 2, "deletions": 0}]
        self.code = [{**self.doc[0], "filename": "scripts/model.py"}]

    def test_docs_are_eligible(self):
        self.assertTrue(evaluate(self.pr, self.doc, [])[0])

    def test_code_requires_independent_fresh_approval(self):
        self.assertFalse(evaluate(self.pr, self.code, [])[0])
        approval = {"user": "reviewer", "state": "APPROVED",
                    "submitted_at": "2026-11-04T07:01:00Z"}
        self.assertTrue(evaluate(self.pr, self.code, [approval])[0])
        self.assertFalse(evaluate(self.pr, self.code, [{**approval, "user": "author"}])[0])
        self.assertFalse(evaluate(self.pr, self.code, [{**approval, "submitted_at": "2026-11-04T06:00:00Z"}])[0])
        self.assertFalse(evaluate(self.pr, self.code, [approval, {**approval, "state": "CHANGES_REQUESTED", "submitted_at": "2026-11-04T07:02:00Z"}])[0])

    def test_other_reviewer_change_request_blocks_approval(self):
        approval = {"user": "reviewer1", "state": "APPROVED",
                    "submitted_at": "2026-11-04T07:02:00Z"}
        request = {"user": "reviewer2", "state": "CHANGES_REQUESTED",
                   "submitted_at": "2026-11-04T07:03:00Z"}
        self.assertFalse(evaluate(self.pr, self.code, [approval, request])[0])

    def test_invalid_metadata_blocks(self):
        self.assertFalse(evaluate({**self.pr, "changed_files": None}, self.doc, [])[0])
        self.assertFalse(evaluate(self.pr, [], [])[0])
        self.assertFalse(evaluate(self.pr, self.code, [{"state": "APPROVED"}])[0])


if __name__ == "__main__":
    unittest.main()
