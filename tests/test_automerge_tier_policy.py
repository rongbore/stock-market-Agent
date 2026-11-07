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

    def test_tests_require_manual_review(self):
        result = self.check([file("tests/test_quality.py")])
        self.assertEqual(result["tier"], "manual")
        self.assertEqual(result["reason"], "non_documentation_changes_require_manual_review")
        self.assertFalse(result["auto_merge_authorized"])

    def test_financial_and_security_changes_require_manual_review(self):
        for path in ("scripts/financial_evidence_quality.py", "config/security.yaml",
                     ".github/workflows/permissions.yml"):
            with self.subTest(path=path):
                result = self.check([file(path)])
                self.assertEqual(result["tier"], "manual")
                self.assertFalse(result["auto_merge_authorized"])

    def test_workflow_change_manual(self):
        self.assertEqual(self.check([file(".github/workflows/test.yml")])["tier"], "manual")

    def test_mixed_code_and_test_manual(self):
        self.assertEqual(self.check([file("tests/test_a.py"), file("scripts/main.py")])["tier"], "manual")

    def test_missing_pagination_manual(self):
        self.assertEqual(self.check([file("docs/a.md")], expected=2)["tier"], "manual")

    def test_documentation_size_limits_match_repository_classifier(self):
        self.assertEqual(self.check([file(f"docs/{i}.md") for i in range(21)])["tier"], "manual")
        self.assertEqual(self.check([file("docs/large.md", additions=301, deletions=0)])["tier"], "manual")

    def test_rename_manual(self):
        self.assertEqual(self.check([file("docs/a.md", status="renamed")])["tier"], "manual")

    def test_negative_counts_manual(self):
        self.assertEqual(self.check([file("docs/a.md", additions=-1)])["tier"], "manual")

    def test_traversal_manual(self):
        self.assertEqual(self.check([file("docs/../test.md")])["tier"], "manual")

    def test_no_candidate_is_authorization(self):
        for p in ("docs/a.md", "tests/test_a.py", "scripts/financial_metric_citations.py",
                  "config/security.yaml"):
            self.assertFalse(self.check([file(p)])["auto_merge_authorized"])


if __name__ == "__main__":
    unittest.main()
