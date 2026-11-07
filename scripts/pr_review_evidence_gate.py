"""Read-only AI review evidence gate for privileged merge controllers.

A candidate is NOT merge authorization. Controllers must independently fetch
current GitHub metadata immediately before merging and enforce branch rules.
"""
import re

_SHA = re.compile(r"^[0-9a-f]{40}$")
_DIGEST = re.compile(r"^[0-9a-f]{64}$")


def assess_review_evidence(*, current_head_sha, current_base_sha,
                           reviewed_head_sha, reviewed_base_sha,
                           review, expected_digest):
    """Return (status, reason) without invoking a provider or merging."""
    for value in (current_head_sha, current_base_sha,
                  reviewed_head_sha, reviewed_base_sha):
        if not isinstance(value, str) or not _SHA.fullmatch(value):
            return "manual", "invalid commit evidence"
    if (current_head_sha != reviewed_head_sha
            or current_base_sha != reviewed_base_sha):
        return "manual", "review evidence is stale"
    if not isinstance(expected_digest, str) or not _DIGEST.fullmatch(expected_digest):
        return "manual", "invalid review digest"
    if not isinstance(review, dict):
        return "manual", "missing review evidence"
    if review.get("head_sha") != current_head_sha:
        return "manual", "review head mismatch"
    if review.get("base_sha") != current_base_sha:
        return "manual", "review base mismatch"
    if review.get("request_digest") != expected_digest:
        return "manual", "review digest mismatch"
    if review.get("verdict") != "approve":
        return "manual", "review did not approve"
    if review.get("evidence_authenticated") is not True:
        return "manual", "review evidence not independently authenticated"
    if review.get("findings") != []:
        return "manual", "unresolved review findings"
    return "candidate", "review evidence matches; revalidate all merge gates"
