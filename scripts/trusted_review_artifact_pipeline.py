"""Compose trusted GitHub artifact checks and review evidence verification.

The caller must source run, artifact, and PR metadata from authenticated
GitHub APIs and supply trusted workflow identity from protected configuration.
This module is offline and never authorizes a merge.
"""
import hashlib

from scripts.github_review_artifact_preflight import assess_provenance
from scripts.safe_review_artifact import verify_review_artifact_archive
from scripts.trusted_review_evidence_verifier import verify_review_evidence

_MAX_ARCHIVE_BYTES = 1024 * 1024


def verify_trusted_review_artifact(*, archive_bytes, repo, current_pr_number,
                                   current_head_sha,
                                   current_base_sha, expected_request_digest,
                                   expected_workflow_id, expected_workflow_path,
                                   expected_event, trusted_artifact_sha,
                                   trusted_workflow_ref, trusted_workflow_sha,
                                   run, artifact):
    """Return a read-only verdict after checking provenance, bytes, and schema."""
    if (not isinstance(archive_bytes, bytes) or
            not 0 < len(archive_bytes) <= _MAX_ARCHIVE_BYTES):
        return {"status": "manual", "reason": "invalid downloaded artifact",
                "evidence_authenticated": False, "merge_authorized": False}
    downloaded_digest = "sha256:" + hashlib.sha256(archive_bytes).hexdigest()
    status, reason = assess_provenance(
        repo=repo, expected_head_sha=current_head_sha,
        expected_workflow_id=expected_workflow_id,
        expected_workflow_path=expected_workflow_path,
        expected_event=expected_event, run=run, artifact=artifact,
        downloaded_artifact_digest=downloaded_digest)
    if status != "candidate":
        return {"status": "manual", "reason": reason,
                "evidence_authenticated": False, "merge_authorized": False}
    try:
        parsed = verify_review_artifact_archive(archive_bytes, artifact.get("digest"))
    except (TypeError, ValueError):
        return {"status": "manual", "reason": "artifact content validation failed",
                "evidence_authenticated": False, "merge_authorized": False}
    evidence = parsed["evidence"]
    review_status, review_reason = verify_review_evidence(
        current_pr_number=current_pr_number, current_head_sha=current_head_sha,
        current_base_sha=current_base_sha,
        expected_request_digest=expected_request_digest, evidence=evidence,
        trusted_artifact_sha=trusted_artifact_sha, trusted_run_id=run.get("id"),
        trusted_repository=repo, trusted_workflow_path=expected_workflow_path,
        trusted_workflow_ref=trusted_workflow_ref,
        trusted_workflow_sha=trusted_workflow_sha, trusted_event=expected_event)
    if review_status != "candidate":
        return {"status": "manual", "reason": review_reason,
                "evidence_authenticated": False, "merge_authorized": False}
    return {"status": "candidate", "reason": "trusted artifact and review evidence verified",
            "evidence": evidence, "evidence_authenticated": True,
            "merge_authorized": False}
