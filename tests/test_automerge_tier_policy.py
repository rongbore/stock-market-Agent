import unittest
from scripts.automerge_tier_policy import classify_tier


def file(path, **kw):
    d = {"filename": path, "status": "modified", "additions": 4, "deletions": 2}
    d.update(kw)
    return d


class TierPolicyTests(unittest.TestCase):
    def check(self, paths, expected=None):
        return classify_tier(paths, expected_count=len(paths) if expected is None else expected)

    def test_docs(self):
        self.assertEqual(self.check([file("docs/guide.md")])["tier"], "documentation_candidate")

    def test_tests(self):
        self.assertEqual(self.check([file("tests/test_quality.py")])["tier"], "tests_candidate")

    def test_financial_requires_independent_validation(self):
        result = self.check([file("scripts/financial_evidence_quality.py")])
        self.assertEqual(result["tier"], "financial_algorithm_requires_independent_validation")
        self.assertFalse(result["auto_merge_authorized"])

    def test_workflow_change_manual(self):
        self.assertEqual(self.check([file(".github/workflows/test.yml")])["tier"], "manual")

    def test_mixed_code_and_test_manual(self):
        self.assertEqual(self.check([file("tests/test_a.py"), file("scripts/main.py")])["tier"], "manual")

    def test_missing_pagination_manual(self):
        self.assertEqual(self.check([file("docs/a.md")], expected=2)["tier"], "manual")

    def test_rename_manual(self):
        self.assertEqual(self.check([file("docs/a.md", status="renamed")])["tier"], "manual")

    def test_negative_counts_manual(self):
        self.assertEqual(self.check([file("docs/a.md", additions=-1)])["tier"], "manual")

    def test_traversal_manual(self):
        self.assertEqual(self.check([file("docs/../test.md")])["tier"], "manual")

    def test_no_candidate_is_authorization(self):
        for p in ("docs/a.md", "tests/test_a.py", "scripts/financial_metric_citations.py"):
            self.assertFalse(self.check([file(p)])["auto_merge_authorized"])


if __name__ == "__main__":
    unittest.main()
