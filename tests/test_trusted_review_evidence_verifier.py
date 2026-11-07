"""Offline tests for review evidence metadata verifier."""
import unittest
from scripts.trusted_review_evidence_verifier import verify_review_evidence

HEAD = "a" * 40
BASE = "b" * 40
ARTIFACT = "c" * 40
DIGEST = "d" * 64


def valid():
    return dict(head_sha=HEAD, base_sha=BASE, artifact_sha=ARTIFACT,
                workflow_run_id=123, request_digest=DIGEST,
                verdict="approve", findings=[])


def check(evidence=None, **changes):
    params = dict(current_head_sha=HEAD, current_base_sha=BASE,
                  expected_request_digest=DIGEST, evidence=valid() if evidence is None else evidence,
                  trusted_artifact_sha=ARTIFACT, trusted_run_id=123)
    params.update(changes)
    return verify_review_evidence(**params)[0]


class TrustedReviewEvidenceVerifierTests(unittest.TestCase):
    def test_matching_metadata_is_only_candidate(self):
        self.assertEqual(check(), "candidate")

    def test_changed_trusted_metadata_blocks(self):
        for key, value in (("current_head_sha", "e" * 40),
                           ("current_base_sha", "e" * 40),
                           ("trusted_artifact_sha", "e" * 40),
                           ("trusted_run_id", 124),
                           ("expected_request_digest", "e" * 64)):
            with self.subTest(key=key):
                self.assertEqual(check(**{key: value}), "manual")

    def test_modified_evidence_blocks(self):
        for key, value in (("head_sha", "e" * 40), ("base_sha", "e" * 40),
                           ("artifact_sha", "e" * 40), ("workflow_run_id", 124),
                           ("request_digest", "e" * 64), ("verdict", "uncertain"),
                           ("findings", [{"severity": "high"}])):
            with self.subTest(key=key):
                evidence = valid()
                evidence[key] = value
                self.assertEqual(check(evidence=evidence), "manual")

    def test_invalid_inputs_block(self):
        self.assertEqual(check(evidence={}), "manual")
        self.assertEqual(check(evidence="approve"), "manual")
        self.assertEqual(check(trusted_run_id=True), "manual")
        self.assertEqual(check(current_head_sha="invalid"), "manual")


if __name__ == "__main__":
    unittest.main()
