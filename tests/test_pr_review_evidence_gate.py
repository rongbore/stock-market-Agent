"""Offline tests for SHA-bound review gate."""
import unittest

from scripts.pr_review_evidence_gate import assess_review_evidence

HEAD = "a" * 40
BASE = "b" * 40
DIGEST = "c" * 64


def evidence():
    return dict(head_sha=HEAD, base_sha=BASE, request_digest=DIGEST,
                verdict="approve", evidence_authenticated=True, findings=[])


def assess(review=None, **changes):
    params = dict(current_head_sha=HEAD, current_base_sha=BASE,
                  reviewed_head_sha=HEAD, reviewed_base_sha=BASE,
                  review=evidence() if review is None else review,
                  expected_digest=DIGEST)
    params.update(changes)
    return assess_review_evidence(**params)[0]


class ReviewEvidenceGateTests(unittest.TestCase):
    def test_current_authenticated_evidence_is_only_candidate(self):
        self.assertEqual(assess(), "candidate")

    def test_head_or_base_changed_blocks(self):
        for field in ("current_head_sha", "current_base_sha",
                      "reviewed_head_sha", "reviewed_base_sha"):
            with self.subTest(field=field):
                self.assertEqual(assess(**{field: "d" * 40}), "manual")

    def test_untrusted_and_unapproved_review_blocks(self):
        for key, value in (("evidence_authenticated", False),
                           ("verdict", "uncertain"),
                           ("findings", [{"severity": "high"}]),
                           ("head_sha", "d" * 40),
                           ("base_sha", "d" * 40),
                           ("request_digest", "d" * 64)):
            with self.subTest(key=key):
                record = evidence()
                record[key] = value
                self.assertEqual(assess(review=record), "manual")

    def test_missing_and_malformed_evidence_blocks(self):
        self.assertEqual(assess(review={}), "manual")
        self.assertEqual(assess(review="approved"), "manual")
        self.assertEqual(assess(expected_digest="bad"), "manual")
        self.assertEqual(assess(current_head_sha=None), "manual")


if __name__ == "__main__":
    unittest.main()
