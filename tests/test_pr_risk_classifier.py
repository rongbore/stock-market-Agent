import unittest
from scripts.pr_risk_classifier import classify


def file(path="docs/guide.md", status="modified", additions=4, deletions=1):
    return {"filename": path, "status": status,
            "additions": additions, "deletions": deletions}


class RiskClassifierTests(unittest.TestCase):
    def test_documentation_only_candidate(self):
        self.assertEqual(classify([file(), file("docs/setup/intro.md")])[0], "eligible")

    def test_sensitive_or_unknown_paths_require_manual_review(self):
        for path in ("README.md", ".github/workflows/ci.yml", "scripts/source_records.py",
                     "tests/test_source_records.py", "docs/../scripts/attack.md",
                     "docs/.hidden.md", "docs/guide.yml", "docs\\guide.md",
                     "docs//guide.md", "docs/./guide.md", "docs/a\nguide.md",
                     "docs/a\tguide.md"):
            with self.subTest(path=path):
                self.assertEqual(classify([file(path)])[0], "manual")

    def test_confusable_paths_and_rename_metadata_require_review(self):
        for path in ("docs/Guide.md", "docs/ｇuide.md", "docs/报告.md",
                     "docs/a​.md"):
            with self.subTest(path=path):
                self.assertEqual(classify([file(path)])[0], "manual")
        renamed = file()
        renamed["previous_filename"] = "scripts/source_records.py"
        self.assertEqual(classify([renamed])[0], "manual")

    def test_deletions_renames_and_unknown_status_require_review(self):
        for status in ("removed", "renamed", "copied", None):
            with self.subTest(status=status):
                self.assertEqual(classify([file(status=status)])[0], "manual")

    def test_size_and_malformed_inputs_fail_closed(self):
        for items in ([], [file()] * 21, [file(additions=301)],
                      [file(additions="1")], [file(deletions=-1)],
                      [{"filename": "docs/a.md", "status": "modified"}],
                      "docs/a.md", [None]):
            with self.subTest(items=items):
                self.assertEqual(classify(items)[0], "manual")


if __name__ == "__main__":
    unittest.main()
