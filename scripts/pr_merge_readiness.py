"""Read-only, fail-closed PR merge readiness assessment.

This module never calls GitHub or merges code. Inputs must be fetched from
trusted APIs by a future privileged controller immediately before use.
"""
from scripts.pr_risk_classifier import classify

REQUIRED_CHECKS = frozenset({"unit-tests", "merge-policy"})


def assess(pr, files, checks, *, protected=False):
    if not isinstance(pr, dict) or not isinstance(checks, list):
        return "manual", "invalid PR or check metadata"
    if protected is not True:
        return "manual", "main branch protection not independently verified"
    if pr.get("base") != "main" or pr.get("state") != "open":
        return "manual", "unexpected target branch or PR state"
    if pr.get("draft") is not False:
        return "manual", "draft or unknown draft status"
    if pr.get("mergeable") is not True:
        return "manual", "mergeability not confirmed"
    head = pr.get("head_sha")
    if not isinstance(head, str) or len(head) != 40 or any(c not in "0123456789abcdef" for c in head):
        return "manual", "invalid head SHA"
    decision, reason = classify(files, expected_count=pr.get("changed_files"))
    if decision != "eligible":
        return "manual", reason
    seen = set()
    for check in checks:
        if not isinstance(check, dict):
            return "manual", "invalid check record"
        name = check.get("name")
        if not isinstance(name, str):
            return "manual", "invalid check name"
        if name not in REQUIRED_CHECKS:
            continue
        if name in seen:
            return "manual", "ambiguous duplicate required check"
        seen.add(name)
        if (check.get("head_sha") != head or check.get("status") != "completed"
                or check.get("conclusion") != "success"):
            return "manual", "required check not successful on current head"
    if seen != REQUIRED_CHECKS:
        return "manual", "missing required check"
    return "candidate", "read-only candidate; privileged controller must revalidate"


if __name__ == "__main__":
    raise SystemExit("Import assess() from a trusted controller; no merge command is provided")
