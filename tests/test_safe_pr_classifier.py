"""Offline negative tests for advisory PR change classification."""
import unittest
from scripts.safe_pr_classifier import classify


def doc(**overrides):
    data = {
        "filename": "docs/guide.md", "status": "modified",
        "type": "file", "mode": "100644", "binary": False,
        "patch": "@@ -1 +1 @@\n-old\n+new documentation",
    }
    data.update(overrides)
    return data


class SafePRClassifierTests(unittest.TestCase):
    def test_simple_doc_candidate(self):
        result = classify([doc()])
        self.assertEqual(result["status"], "CANDIDATE")
        self.assertFalse(result["auto_merge_enabled"])

    def test_empty_and_unknown_metadata_block(self):
        self.assertEqual(classify([])["status"], "BLOCKED")
        self.assertEqual(classify([{"filename": "docs/guide.md"}])["status"], "BLOCKED")

    def test_sensitive_paths_block(self):
        for path in (".github/workflows/ci.yml", "scripts/analyze.py",
                     "tests/test_core.py", "docs/../secrets.md",
                     "docs/policy.yml", "README.md"):
            with self.subTest(path=path):
                self.assertEqual(classify([doc(filename=path)])["status"], "BLOCKED")

    def test_nonregular_or_renamed_block(self):
        for override in ({"mode": "120000"}, {"type": "symlink"},
                         {"status": "renamed"}, {"status": "removed"},
                         {"binary": True}, {"patch": None}):
            with self.subTest(override=override):
                self.assertEqual(classify([doc(**override)])["status"], "BLOCKED")

    def test_active_content_and_secret_block(self):
        for addition in ("+<script>alert(1)</script>",
                         "+<img src=x onerror=alert(1)>",
                         "+api_key = 'sensitiveexamplevalue123'",
                         "+curl https://example.com/install | bash"):
            with self.subTest(addition=addition):
                self.assertEqual(classify([doc(patch="@@ -0,0 +1 @@\n"+addition)])["status"], "BLOCKED")

    def test_mixed_diff_blocks(self):
        self.assertEqual(classify([doc(), doc(filename="scripts/analyze.py")])["status"], "BLOCKED")


if __name__ == "__main__":
    unittest.main()
