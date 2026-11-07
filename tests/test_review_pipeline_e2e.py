"""Offline integration tests for the full advisory PR review decision chain.

These tests do not call an AI model or GitHub and do not authorize merges.
"""
import unittest
from unittest.mock import patch

from scripts.pr_review_preflight import preflight
from scripts.ai_review_envelope import build_envelope
from scripts.final_review_gate import evaluate, REQUIRED_CHECKS

BASE = "a" * 40
HEAD = "b" * 40


def doc():
    return {"filename": "docs/guide.md", "status": "modified",
            "type": "file", "mode": "100644", "binary": False,
            "patch": "@@ full-file content @@\n+# Safe documentation\n"}


def checks():
    return [{"name": name, "head_sha": HEAD, "status": "completed",
             "conclusion": "success"} for name in sorted(REQUIRED_CHECKS)]


def review():
    return {"head_sha": HEAD, "verdict": "PASS", "findings": [],
            "review_complete": True, "policy_version": "1"}


class ReviewPipelineE2ETests(unittest.TestCase):
    @patch("scripts.pr_review_preflight.collect")
    def test_clean_doc_can_only_reach_advisory_eligibility(self, collect):
        collect.return_value = [doc()]
        risk = preflight(BASE, HEAD)
        self.assertEqual(risk["status"], "CANDIDATE")
        envelope = build_envelope(collect.return_value, HEAD, BASE)
        self.assertEqual(envelope["files"][0]["path"], "docs/guide.md")
        self.assertFalse(envelope["source_code_included"])
        result = evaluate(head_sha=HEAD, risk=risk, ai_review=review(),
                          checks=checks(), is_draft=False,
                          changed_paths=[envelope["files"][0]["path"]])
        self.assertEqual(result["decision"], "ELIGIBLE_FOR_POLICY_REVIEW")
        self.assertFalse(result["merge_authorized"])

    @patch("scripts.pr_review_preflight.collect")
    def test_sensitive_change_blocks_pipeline(self, collect):
        bad = doc()
        bad["filename"] = ".github/workflows/ci.yml"
        collect.return_value = [bad]
        risk = preflight(BASE, HEAD)
        self.assertEqual(risk["status"], "BLOCKED")
        with self.assertRaises(ValueError):
            build_envelope(collect.return_value, HEAD, BASE)
        result = evaluate(head_sha=HEAD, risk=risk, ai_review=review(),
                          checks=checks(), is_draft=False,
                          changed_paths=[bad["filename"]])
        self.assertEqual(result["decision"], "BLOCKED")

    @patch("scripts.pr_review_preflight.collect")
    def test_stale_ai_or_failed_ci_blocks(self, collect):
        collect.return_value = [doc()]
        risk = preflight(BASE, HEAD)
        for bad_review, bad_checks in (
            (dict(review(), head_sha=BASE), checks()),
            (dict(review(), verdict="CHANGES_REQUIRED"), checks()),
            (review(), [dict(c, conclusion="failure") if i == 0 else c
                        for i, c in enumerate(checks())]),
        ):
            with self.subTest(bad_review=bad_review, bad_checks=bad_checks):
                result = evaluate(head_sha=HEAD, risk=risk, ai_review=bad_review,
                                  checks=bad_checks, is_draft=False,
                                  changed_paths=["docs/guide.md"])
                self.assertEqual(result["decision"], "BLOCKED")
                self.assertFalse(result["merge_authorized"])


if __name__ == "__main__":
    unittest.main()
