"""Pure, read-only verification of review evidence against trusted metadata.

The trusted caller must obtain current PR metadata and the evidence envelope
from authenticated GitHub APIs, not a PR comment or model-produced JSON.
This does not authenticate the origin of an envelope by itself.
"""
import hmac
import re

_SHA = re.compile(r"^[0-9a-f]{40}$")
_DIGEST = re.compile(r"^[0-9a-f]{64}$")


def verify_review_evidence(*, current_head_sha, current_base_sha,
                           expected_request_digest, evidence,
                           trusted_artifact_sha, trusted_run_id):
    """Return (status, reason); never grant merge permission."""
    if any(not isinstance(v, str) or not _SHA.fullmatch(v)
           for v in (current_head_sha, current_base_sha, trusted_artifact_sha)):
        return "manual", "invalid trusted commit metadata"
    if (not isinstance(expected_request_digest, str)
            or not _DIGEST.fullmatch(expected_request_digest)):
        return "manual", "invalid expected request digest"
    if type(trusted_run_id) is not int or trusted_run_id <= 0:
        return "manual", "invalid trusted workflow run"
    if not isinstance(evidence, dict):
        return "manual", "missing review evidence"
    if evidence.get("head_sha") != current_head_sha:
        return "manual", "review head is stale"
    if evidence.get("base_sha") != current_base_sha:
        return "manual", "review base is stale"
    if evidence.get("artifact_sha") != trusted_artifact_sha:
        return "manual", "artifact SHA mismatch"
    if evidence.get("workflow_run_id") != trusted_run_id:
        return "manual", "workflow run mismatch"
    digest = evidence.get("request_digest")
    if not isinstance(digest, str) or not _DIGEST.fullmatch(digest):
        return "manual", "missing review digest"
    if not hmac.compare_digest(digest, expected_request_digest):
        return "manual", "review request digest mismatch"
    if evidence.get("verdict") != "approve" or evidence.get("findings") != []:
        return "manual", "review not cleanly approved"
    return "candidate", "metadata matches; artifact provenance still requires independent verification"
