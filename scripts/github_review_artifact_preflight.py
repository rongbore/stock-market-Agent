"""Fail-closed GitHub Actions artifact provenance preflight (read-only).

All inputs must be obtained from authenticated GitHub API responses by a
privileged controller. Matching metadata alone is NOT cryptographic proof.
No network access, artifact download, credential handling, or merging.
"""
import re

_SHA = re.compile(r"^[0-9a-f]{40}$")


def assess_provenance(*, repo, expected_head_sha, expected_workflow_id,
                      run, artifact):
    """Return (status, reason); candidate never means merge authorization."""
    if repo != "rongbore/stock-market-Agent":
        return "manual", "unexpected repository"
    if not isinstance(expected_head_sha, str) or not _SHA.fullmatch(expected_head_sha):
        return "manual", "invalid expected commit"
    if type(expected_workflow_id) is not int or expected_workflow_id <= 0:
        return "manual", "invalid workflow identifier"
    if not isinstance(run, dict) or not isinstance(artifact, dict):
        return "manual", "missing GitHub API metadata"
    if run.get("repository_full_name") != repo:
        return "manual", "workflow repository mismatch"
    if run.get("head_sha") != expected_head_sha:
        return "manual", "workflow commit mismatch"
    if type(run.get("workflow_id")) is not int or run["workflow_id"] != expected_workflow_id:
        return "manual", "unexpected workflow"
    if run.get("event") not in ("pull_request", "workflow_dispatch"):
        return "manual", "unexpected workflow event"
    if run.get("status") != "completed" or run.get("conclusion") != "success":
        return "manual", "workflow not successful"
    if type(run.get("id")) is not int or run["id"] <= 0:
        return "manual", "invalid workflow run ID"
    if type(artifact.get("workflow_run_id")) is not int or artifact["workflow_run_id"] != run["id"]:
        return "manual", "artifact from different run"
    if type(artifact.get("id")) is not int or artifact["id"] <= 0:
        return "manual", "invalid artifact ID"
    if artifact.get("expired") is not False:
        return "manual", "artifact expired or unknown"
    if type(artifact.get("size_in_bytes")) is not int or not 0 < artifact["size_in_bytes"] <= 1048576:
        return "manual", "artifact size invalid or excessive"
    if artifact.get("name") != "ai-review-evidence":
        return "manual", "unexpected artifact name"
    return "candidate", "metadata matches; authenticate artifact contents separately"
