import unittest
from unittest.mock import patch

from scripts.pr_review_preflight import preflight


def safe_change():
    return {"filename": "docs/guide.md", "status": "modified",
            "type": "file", "mode": "100644", "binary": False,
            "patch": "@@ full-file content @@\n+Safe documentation\n"}


class PreflightTests(unittest.TestCase):
    @patch("scripts.pr_review_preflight.collect")
    def test_candidate_is_never_merge_permission(self, collect):
        collect.return_value = [safe_change()]
        result = preflight("a" * 40, "b" * 40)
        self.assertEqual(result["status"], "CANDIDATE")
        self.assertTrue(result["review_required"])
        self.assertFalse(result["merge_authorized"])

    @patch("scripts.pr_review_preflight.collect")
    def test_sensitive_change_is_blocked(self, collect):
        item = safe_change()
        item["filename"] = ".github/workflows/ci.yml"
        collect.return_value = [item]
        self.assertEqual(preflight("a" * 40, "b" * 40)["status"], "BLOCKED")

    @patch("scripts.pr_review_preflight.collect")
    def test_failed_collection_blocks(self, collect):
        collect.side_effect = ValueError("incomplete diff")
        result = preflight("a" * 40, "b" * 40)
        self.assertEqual(result["status"], "BLOCKED")
        self.assertFalse(result["merge_authorized"])


if __name__ == "__main__":
    unittest.main()
