"""Strict parser for untrusted AI PR-review output.

An AI PASS is advisory. It never grants permission to merge.
"""
import argparse
import json

VERDICTS = frozenset({"PASS", "CHANGES_REQUIRED", "BLOCKED"})
SEVERITIES = frozenset({"info", "low", "medium", "high", "critical"})


def validate_review(value, expected_head_sha):
    reasons = []
    if not isinstance(value, dict):
        return {"status": "BLOCKED", "reasons": ["invalid_review_object"], "merge_authorized": False}
    if not isinstance(expected_head_sha, str) or len(expected_head_sha) != 40 or any(c not in "0123456789abcdef" for c in expected_head_sha):
        reasons.append("invalid_expected_sha")
    if value.get("head_sha") != expected_head_sha:
        reasons.append("stale_or_missing_head_sha")
    verdict = value.get("verdict")
    if verdict not in VERDICTS:
        reasons.append("invalid_verdict")
    findings = value.get("findings")
    if not isinstance(findings, list) or len(findings) > 100:
        reasons.append("invalid_findings")
        findings = []
    for index, finding in enumerate(findings):
        if not isinstance(finding, dict) or finding.get("severity") not in SEVERITIES or not isinstance(finding.get("message"), str) or not finding["message"].strip():
            reasons.append(f"invalid_finding_{index}")
    if verdict == "PASS" and findings:
        reasons.append("pass_with_findings")
    if value.get("review_complete") is not True:
        reasons.append("incomplete_review")
    if value.get("policy_version") != "1":
        reasons.append("unknown_policy_version")
    status = "BLOCKED" if reasons else verdict
    return {"status": status, "reasons": reasons, "merge_authorized": False}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("review_json")
    parser.add_argument("--head-sha", required=True)
    args = parser.parse_args()
    try:
        with open(args.review_json, encoding="utf-8") as handle:
            review = json.load(handle)
        result = validate_review(review, args.head_sha)
    except (OSError, ValueError, UnicodeError):
        result = {"status": "BLOCKED", "reasons": ["unreadable_review"], "merge_authorized": False}
    print(json.dumps(result, ensure_ascii=False))
    raise SystemExit(0 if result["status"] == "PASS" else 1)


if __name__ == "__main__":
    main()
