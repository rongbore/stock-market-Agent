"""Regression tests for fail-closed merge readiness (Issue #209).

Tests exercise the read-only assessor; they do not authorize or execute merges.
"""
import unittest
from unittest.mock import patch

from scripts.pr_merge_readiness import assess


HEAD = "a" * 40
STALE = "b" * 40


def pr():
    return {
        "base": "main", "state": "open", "draft": False,
        "mergeable": True, "head_sha": HEAD, "changed_files": 1,
    }


def checks(sha=HEAD):
    return [
        {"name": name, "head_sha": sha, "status": "completed",
         "conclusion": "success"}
        for name in ("unit-tests", "merge-policy")
    ]


class MergeReadinessFailClosedTests(unittest.TestCase):
    def assess_with_eligible_files(self, metadata, records):
        # Isolate the freshness/CI checks from the path classifier.
        with patch("scripts.pr_merge_readiness.classify",
                   return_value=("eligible", "allowed")):
            return assess(metadata, [{"filename": "docs/guide.md"}],
                          records, protected=True)

    def test_current_checks_are_only_a_candidate(self):
        decision, reason = self.assess_with_eligible_files(pr(), checks())
        self.assertEqual(decision, "candidate")
        self.assertIn("revalidate", reason)

    def test_stale_head_checks_block(self):
        self.assertEqual(self.assess_with_eligible_files(
            pr(), checks(STALE))[0], "manual")

    def test_partial_checks_block(self):
        self.assertEqual(self.assess_with_eligible_files(
            pr(), checks()[:1])[0], "manual")

    def test_duplicate_required_check_blocks(self):
        records = checks() + [checks()[0]]
        self.assertEqual(self.assess_with_eligible_files(
            pr(), records)[0], "manual")

    def test_pending_failed_and_unknown_checks_block(self):
        for status, conclusion in (
            ("in_progress", None), ("completed", "failure"),
            ("completed", None), ("queued", "success"),
        ):
            with self.subTest(status=status, conclusion=conclusion):
                records = checks()
                records[0]["status"] = status
                records[0]["conclusion"] = conclusion
                self.assertEqual(self.assess_with_eligible_files(
                    pr(), records)[0], "manual")

    def test_draft_and_unknown_mergeability_block(self):
        for field, value in (("draft", True), ("draft", None),
                             ("mergeable", False), ("mergeable", None)):
            with self.subTest(field=field, value=value):
                metadata = pr()
                metadata[field] = value
                self.assertEqual(self.assess_with_eligible_files(
                    metadata, checks())[0], "manual")

    def test_unprotected_branch_blocks(self):
        with patch("scripts.pr_merge_readiness.classify",
                   return_value=("eligible", "allowed")):
            decision, _ = assess(pr(), [{}], checks(), protected=False)
        self.assertEqual(decision, "manual")


if __name__ == "__main__":
    unittest.main()
