"""Pure, fail-closed readiness evaluation for future trusted auto-merge controller.

No network access, token use, GitHub merge operations, or AI invocation.
Caller-supplied evidence is NOT authenticated by this function.
"""
import re

SHA = re.compile(r"^[0-9a-f]{40}$")
REQUIRED = frozenset({"unit-tests", "merge-policy"})
TIERS = frozenset({"documentation_candidate"})


def evaluate_readiness(*, tier_result, pr, checks, review,
                       review_threads, has_changes_requested_review,
                       current_base_sha, checks_complete,
                       expected_check_count, review_threads_complete):
    reasons = []
    if not isinstance(tier_result, dict) or tier_result.get("tier") not in TIERS:
        reasons.append("unapproved_change_tier")
    if not isinstance(pr, dict):
        pr = {}
    sha = pr.get("head_sha")
    if not isinstance(sha, str) or not SHA.fullmatch(sha):
        reasons.append("invalid_head_sha")
    if pr.get("draft") is not False or pr.get("state") != "open":
        reasons.append("draft_or_closed_pr")
    if pr.get("base_ref") != "main":
        reasons.append("wrong_base")
    pr_base_sha = pr.get("base_sha")
    if (not isinstance(pr_base_sha, str) or not SHA.fullmatch(pr_base_sha) or
            not isinstance(current_base_sha, str) or not SHA.fullmatch(current_base_sha) or
            pr_base_sha != current_base_sha):
        reasons.append("base_not_current_or_unverified")
    base_repo = pr.get("base_repo_full_name")
    head_repo = pr.get("head_repo_full_name")
    if (not isinstance(base_repo, str) or not base_repo.strip() or
            not isinstance(head_repo, str) or not head_repo.strip() or
            base_repo.casefold() != head_repo.casefold()):
        reasons.append("fork_or_unverified_head_repository")
    if pr.get("mergeable") is not True:
        reasons.append("mergeability_not_confirmed")
    if pr.get("head_sha") != pr.get("reviewed_head_sha"):
        reasons.append("reviewed_sha_changed")
    if not isinstance(review, dict) or review.get("head_sha") != sha or review.get("verdict") != "approve" or review.get("trusted") is not True:
        reasons.append("missing_trusted_ai_review")
    if type(has_changes_requested_review) is not bool:
        reasons.append("review_status_missing_or_invalid")
    elif has_changes_requested_review:
        reasons.append("changes_requested_review")
    if review_threads_complete is not True:
        reasons.append("review_threads_incomplete_or_unverified")
    if not isinstance(review_threads, list):
        reasons.append("review_threads_missing_or_invalid")
    else:
        for thread in review_threads:
            if not isinstance(thread, dict) or type(thread.get("is_resolved")) is not bool:
                reasons.append("review_thread_status_missing_or_invalid")
            elif not thread["is_resolved"]:
                reasons.append("unresolved_review_threads")
    if checks_complete is not True:
        reasons.append("check_evidence_incomplete_or_unverified")
    if not isinstance(checks, list):
        checks = []
        reasons.append("missing_checks")
    if type(expected_check_count) is not int or expected_check_count != len(checks):
        reasons.append("check_count_mismatch")
    found = set()
    for c in checks:
        if not isinstance(c, dict) or not isinstance(c.get("name"), str):
            reasons.append("invalid_check")
            continue
        name = c["name"]
        if name in found:
            reasons.append("duplicate_check")
        found.add(name)
        if c.get("head_sha") != sha or c.get("status") != "completed" or c.get("conclusion") != "success":
            reasons.append("stale_pending_or_failed_check")
    if not REQUIRED.issubset(found):
        reasons.append("required_checks_missing")
    return {
        "decision": "READY_FOR_TRUSTED_CONTROLLER" if not reasons else "BLOCKED",
        "reasons": sorted(set(reasons)),
        "merge_authorized": False,
        "evidence_authenticated": False,
    }
