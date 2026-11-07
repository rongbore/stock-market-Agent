"""Pure, fail-closed readiness evaluation for future trusted auto-merge controller.

No network access, token use, GitHub merge operations, or AI invocation.
Caller-supplied evidence is NOT authenticated by this function.
"""
import re

SHA = re.compile(r"^[0-9a-f]{40}$")
REQUIRED = frozenset({"unit-tests", "merge-policy"})
TIERS = frozenset({"documentation_candidate", "tests_candidate",
                   "financial_algorithm_requires_independent_validation"})


def evaluate_readiness(*, tier_result, pr, checks, review, independent_validation=None):
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
    if pr.get("mergeable") is not True:
        reasons.append("mergeability_not_confirmed")
    if pr.get("head_sha") != pr.get("reviewed_head_sha"):
        reasons.append("reviewed_sha_changed")
    if not isinstance(review, dict) or review.get("head_sha") != sha or review.get("verdict") != "approve" or review.get("trusted") is not True:
        reasons.append("missing_trusted_ai_review")
    if not isinstance(checks, list):
        checks = []
        reasons.append("missing_checks")
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
    if tier_result.get("tier") == "financial_algorithm_requires_independent_validation":
        if not isinstance(independent_validation, dict) or independent_validation.get("head_sha") != sha or independent_validation.get("passed") is not True or independent_validation.get("trusted") is not True:
            reasons.append("independent_financial_validation_missing")
    return {
        "decision": "READY_FOR_TRUSTED_CONTROLLER" if not reasons else "BLOCKED",
        "reasons": sorted(set(reasons)),
        "merge_authorized": False,
        "evidence_authenticated": False,
    }
