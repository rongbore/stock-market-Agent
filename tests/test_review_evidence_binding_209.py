"""Fail-closed regression tests for immutable AI review evidence (#209)."""
import unittest
from unittest.mock import patch

from scripts.ai_review_evidence_binding import prepare_review, attach_review


HEAD = "a" * 40
OTHER = "b" * 40


def prepared():
    return prepare_review(
        head_sha=HEAD,
        changed_files=["docs/guide.md"],
        diff="FILE docs/guide.md\n@@ -1 +1 @@\n-old\n+new",
    )


class ReviewEvidenceBindingTests(unittest.TestCase):
    def attach(self, evidence, *, sha=HEAD, digest=None):
        # Keep the adapter parser independent from the binding checks.
        with patch("scripts.ai_review_evidence_binding.parse_review",
                   return_value={"verdict": "approve", "findings": []}):
            return attach_review(
                prepared=evidence, response={"verdict": "approve"},
                expected_head_sha=sha,
                expected_digest=digest if digest is not None
                else evidence["request_digest"],
            )

    def test_valid_evidence_remains_advisory(self):
        result = self.attach(prepared())
        self.assertEqual(result["status"], "ADVISORY_ONLY")
        self.assertFalse(result["merge_authorized"])
        self.assertFalse(result["evidence_authenticated"])

    def test_replay_on_new_head_is_rejected(self):
        with self.assertRaises(ValueError):
            self.attach(prepared(), sha=OTHER)

    def test_modified_request_is_rejected(self):
        evidence = prepared()
        evidence["request"]["head_sha"] = OTHER
        with self.assertRaises(ValueError):
            self.attach(evidence)

    def test_modified_diff_is_rejected(self):
        evidence = prepared()
        evidence["request"]["diff"] = "changed after model review"
        with self.assertRaises(ValueError):
            self.attach(evidence)

    def test_tampered_digest_is_rejected(self):
        evidence = prepared()
        evidence["request_digest"] = "0" * 64
        with self.assertRaises(ValueError):
            self.attach(evidence)

    def test_invalid_expected_digest_is_rejected(self):
        with self.assertRaises(ValueError):
            self.attach(prepared(), digest="not-a-digest")

    def test_invalid_expected_head_is_rejected(self):
        with self.assertRaises(ValueError):
            self.attach(prepared(), sha="not-a-sha")


if __name__ == "__main__":
    unittest.main()
