"""Fail-closed advisory final review gate.

No GitHub API calls, model calls, secrets, or merge operations.
All inputs must be independently obtained from trusted sources.
"""
import argparse
import json
import re

from scripts.ai_review_contract import validate_review

SHA = re.compile(r"^[0-9a-f]{40}$")
REQUIRED_CHECKS = frozenset({
    "Python input tests",
    "AI Review Safety Gate (Phase 1)",
    "PR Risk Preflight (advisory)",
    "Merge policy",
})


def evaluate(*, head_sha, risk, ai_review, checks, is_draft, changed_paths):
    reasons = []
    if not isinstance(head_sha, str) or not SHA.fullmatch(head_sha):
        reasons.append("invalid_head_sha")
    if is_draft is not False:
        reasons.append("draft_or_unknown")
    if not isinstance(changed_paths, list) or not changed_paths:
        reasons.append("missing_changed_paths")
    else:
        # Never authorize merges involving CI, code, config or sensitive files.
        if any(not isinstance(p, str) or not re.fullmatch(
            r"docs/(?:[A-Za-z0-9_-]+/)*[A-Za-z0-9_-]+\.md", p
        ) for p in changed_paths):
            reasons.append("non_documentation_change")
        if len(changed_paths) != len(set(changed_paths)):
            reasons.append("duplicate_paths")
    if not isinstance(risk, dict) or risk.get("status") != "CANDIDATE" or risk.get("head_sha") != head_sha:
        reasons.append("risk_not_current_candidate")
    # Never trust a caller-provided status: validate the raw AI response here.
    if validate_review(ai_review, head_sha).get("status") != "PASS":
        reasons.append("ai_review_not_verified")
    if not isinstance(checks, list):
        reasons.append("invalid_checks")
    else:
        by_name = {}
        for check in checks:
            if not isinstance(check, dict) or not isinstance(check.get("name"), str):
                reasons.append("malformed_check")
                continue
            name = check["name"]
            if name in by_name:
                reasons.append("duplicate_check_name")
            by_name[name] = check
        if not REQUIRED_CHECKS.issubset(by_name):
            reasons.append("missing_required_checks")
        for name, check in by_name.items():
            if check.get("head_sha") != head_sha or check.get("conclusion") != "success" or check.get("status") != "completed":
                reasons.append("failed_stale_or_incomplete_check")
    return {
        "decision": "ELIGIBLE_FOR_POLICY_REVIEW" if not reasons else "BLOCKED",
        "reasons": sorted(set(reasons)),
        "merge_authorized": False,
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("evidence_json")
    args = parser.parse_args()
    try:
        with open(args.evidence_json, encoding="utf-8") as stream:
            data = json.load(stream)
        result = evaluate(**data)
    except (OSError, ValueError, TypeError, UnicodeError):
        result = {"decision": "BLOCKED", "reasons": ["invalid_evidence"], "merge_authorized": False}
    print(json.dumps(result, ensure_ascii=False))
    raise SystemExit(0 if result["decision"] == "ELIGIBLE_FOR_POLICY_REVIEW" else 1)


if __name__ == "__main__":
    main()
