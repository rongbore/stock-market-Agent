"""Pure, read-only verification of review evidence against trusted metadata.

The trusted caller must obtain current PR metadata and the evidence envelope
from authenticated GitHub APIs, not a PR comment or model-produced JSON.
This does not authenticate the origin of an envelope by itself.
"""
import hmac
import re

_SHA = re.compile(r"^[0-9a-f]{40}$")
_DIGEST = re.compile(r"^[0-9a-f]{64}$")


def verify_review_evidence(*, current_pr_number, current_head_sha, current_base_sha,
                           expected_request_digest, evidence,
                           trusted_artifact_sha, trusted_run_id,
                           trusted_repository, trusted_workflow_path,
                           trusted_workflow_ref, trusted_workflow_sha,
                           trusted_event):
    """Return (status, reason); never grant merge permission."""
    if any(not isinstance(v, str) or not _SHA.fullmatch(v)
           for v in (current_head_sha, current_base_sha, trusted_artifact_sha,
                     trusted_workflow_sha)):
        return "manual", "invalid trusted commit metadata"
    if (not isinstance(trusted_repository, str) or
            not re.fullmatch(r"[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+", trusted_repository)):
        return "manual", "invalid trusted repository"
    if (not isinstance(trusted_workflow_path, str) or
            not re.fullmatch(r"\.github/workflows/[A-Za-z0-9_.-]+\.ya?ml", trusted_workflow_path)):
        return "manual", "invalid trusted workflow path"
    if (not isinstance(trusted_workflow_ref, str) or not trusted_workflow_ref.strip() or
            not isinstance(trusted_event, str) or not trusted_event.strip()):
        return "manual", "invalid trusted workflow context"
    if (not isinstance(expected_request_digest, str)
            or not _DIGEST.fullmatch(expected_request_digest)):
        return "manual", "invalid expected request digest"
    if type(trusted_run_id) is not int or trusted_run_id <= 0:
        return "manual", "invalid trusted workflow run"
    if type(current_pr_number) is not int or current_pr_number <= 0:
        return "manual", "invalid trusted pull request number"
    if not isinstance(evidence, dict):
        return "manual", "missing review evidence"
    if type(evidence.get("pr_number")) is not int or evidence["pr_number"] != current_pr_number:
        return "manual", "review pull request mismatch"
    if evidence.get("head_sha") != current_head_sha:
        return "manual", "review head is stale"
    if evidence.get("base_sha") != current_base_sha:
        return "manual", "review base is stale"
    if evidence.get("artifact_sha") != trusted_artifact_sha:
        return "manual", "artifact SHA mismatch"
    if evidence.get("workflow_run_id") != trusted_run_id:
        return "manual", "workflow run mismatch"
    if evidence.get("repository") != trusted_repository:
        return "manual", "workflow repository mismatch"
    if evidence.get("workflow_path") != trusted_workflow_path:
        return "manual", "workflow path mismatch"
    if evidence.get("workflow_ref") != trusted_workflow_ref:
        return "manual", "workflow ref mismatch"
    if evidence.get("workflow_sha") != trusted_workflow_sha:
        return "manual", "workflow source SHA mismatch"
    if evidence.get("event") != trusted_event:
        return "manual", "workflow event mismatch"
    digest = evidence.get("request_digest")
    if not isinstance(digest, str) or not _DIGEST.fullmatch(digest):
        return "manual", "missing review digest"
    if not hmac.compare_digest(digest, expected_request_digest):
        return "manual", "review request digest mismatch"
    if evidence.get("verdict") != "approve" or evidence.get("findings") != []:
        return "manual", "review not cleanly approved"
    return "candidate", "metadata matches; artifact provenance still requires independent verification"
