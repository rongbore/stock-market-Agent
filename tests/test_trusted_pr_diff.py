import unittest
from unittest.mock import patch
from scripts.trusted_pr_diff import collect

BASE = "a" * 40
HEAD = "b" * 40


class TrustedDiffTests(unittest.TestCase):
    def test_invalid_sha_fails_before_git(self):
        with self.assertRaises(ValueError):
            collect("main", HEAD)

    @patch("scripts.trusted_pr_diff.git")
    def test_clean_document(self, run):
        run.side_effect = [BASE.encode(), HEAD.encode(), BASE.encode(),
                           b":000000 100644 " + b"0"*40 + b" " + b"1"*40 + b" A\0docs/guide.md\0",
                           b"# Guide\nSafe text\n"]
        data = collect(BASE, HEAD)
        self.assertEqual(len(data), 1)
        self.assertEqual(data[0]["mode"], "100644")

    @patch("scripts.trusted_pr_diff.git")
    def test_workflow_path_blocked(self, run):
        run.side_effect = [BASE.encode(), HEAD.encode(), BASE.encode(),
                           b":000000 100644 " + b"0"*40 + b" " + b"1"*40 + b" A\0.github/workflows/ci.yml\0"]
        with self.assertRaises(ValueError):
            collect(BASE, HEAD)

    @patch("scripts.trusted_pr_diff.git")
    def test_symlink_blocked(self, run):
        run.side_effect = [BASE.encode(), HEAD.encode(), BASE.encode(),
                           b":000000 120000 " + b"0"*40 + b" " + b"1"*40 + b" A\0docs/link.md\0"]
        with self.assertRaises(ValueError):
            collect(BASE, HEAD)

    @patch("scripts.trusted_pr_diff.git")
    def test_diverged_base_uses_merge_base(self, run):
        ancestor = "c" * 40
        run.side_effect = [BASE.encode(), HEAD.encode(), ancestor.encode(),
                           b":000000 100644 " + b"0"*40 + b" " + b"1"*40 + b" A\\0docs/guide.md\\0",
                           b"# Guide\\n"]
        data = collect(BASE, HEAD)
        self.assertEqual(data[0]["filename"], "docs/guide.md")
        diff_call = run.call_args_list[3].args
        self.assertEqual(diff_call[-2:], (ancestor, HEAD))


if __name__ == "__main__":
    unittest.main()
