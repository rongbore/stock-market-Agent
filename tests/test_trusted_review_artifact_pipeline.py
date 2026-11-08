"""Offline tests for the composed trusted review artifact pipeline."""
import hashlib
import io
import json
import zipfile
import unittest

from scripts.trusted_review_artifact_pipeline import verify_trusted_review_artifact

REPO = "rongbore/stock-market-Agent"
HEAD = "a" * 40
BASE = "b" * 40
ARTIFACT_SHA = "c" * 40
REQUEST_DIGEST = "d" * 64
WORKFLOW_PATH = ".github/workflows/ai-pr-review-manual.yml"
WORKFLOW_REF = REPO + "/" + WORKFLOW_PATH + "@refs/heads/main"
WORKFLOW_SHA = "e" * 40
EVENT = "workflow_dispatch"


def evidence():
    return {"head_sha": HEAD, "base_sha": BASE, "artifact_sha": ARTIFACT_SHA,
            "workflow_run_id": 123, "request_digest": REQUEST_DIGEST,
            "repository": REPO, "workflow_path": WORKFLOW_PATH,
            "workflow_ref": WORKFLOW_REF, "workflow_sha": WORKFLOW_SHA,
            "event": EVENT, "verdict": "approve", "findings": []}


def bundle():
    stream = io.BytesIO()
    with zipfile.ZipFile(stream, "w", zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("ai-review-evidence.json", json.dumps(evidence()))
    return stream.getvalue()


def inputs():
    archive = bundle()
    run = {"repository_full_name": REPO, "head_repository_full_name": REPO,
           "head_sha": HEAD, "workflow_id": 77, "path": WORKFLOW_PATH,
           "event": EVENT, "status": "completed", "conclusion": "success",
           "id": 123, "run_attempt": 1}
    artifact = {"workflow_run_id": 123, "id": 456, "expired": False,
                "size_in_bytes": len(archive), "name": "ai-review-evidence",
                "digest": "sha256:" + hashlib.sha256(archive).hexdigest()}
    return {"archive_bytes": archive, "repo": REPO,
            "current_head_sha": HEAD, "current_base_sha": BASE,
            "expected_request_digest": REQUEST_DIGEST,
            "expected_workflow_id": 77, "expected_workflow_path": WORKFLOW_PATH,
            "expected_event": EVENT, "trusted_artifact_sha": ARTIFACT_SHA,
            "trusted_workflow_ref": WORKFLOW_REF,
            "trusted_workflow_sha": WORKFLOW_SHA, "run": run, "artifact": artifact}


class TrustedReviewArtifactPipelineTests(unittest.TestCase):
    def test_valid_evidence_is_verified_but_never_merge_authorized(self):
        result = verify_trusted_review_artifact(**inputs())
        self.assertEqual(result["status"], "candidate")
        self.assertTrue(result["evidence_authenticated"])
        self.assertFalse(result["merge_authorized"])

    def test_untrusted_workflow_or_stale_evidence_blocks(self):
        args = inputs()
        args["run"] = dict(args["run"], workflow_id=78)
        result = verify_trusted_review_artifact(**args)
        self.assertEqual(result["status"], "manual")
        self.assertFalse(result["evidence_authenticated"])
        args = inputs()
        args["current_head_sha"] = "f" * 40
        result = verify_trusted_review_artifact(**args)
        self.assertEqual(result["status"], "manual")

    def test_digest_mismatch_blocks_before_review_approval(self):
        args = inputs()
        args["artifact"] = dict(args["artifact"], digest="sha256:" + "0" * 64)
        result = verify_trusted_review_artifact(**args)
        self.assertEqual(result["status"], "manual")
        self.assertFalse(result["merge_authorized"])

    def test_invalid_or_oversized_archive_is_rejected_before_hashing(self):
        for value in (b"", bytearray(b"zip"), b"x" * (1024 * 1024 + 1)):
            with self.subTest(value_type=type(value).__name__, size=len(value)):
                args = inputs()
                args["archive_bytes"] = value
                result = verify_trusted_review_artifact(**args)
                self.assertEqual(result["status"], "manual")
                self.assertFalse(result["merge_authorized"])


if __name__ == "__main__":
    unittest.main()
