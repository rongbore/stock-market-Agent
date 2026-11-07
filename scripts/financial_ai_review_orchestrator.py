"""Deterministic orchestration contract for independent finance specialist reviews.

The caller supplies a reviewer callable (e.g. an isolated model invocation).
This module does not perform network I/O, trade, or authorize merges.
"""
import json

from scripts.financial_ai_review_roles import build_specialist_assignments

ALLOWED_VERDICTS = {"approve", "request_changes", "uncertain"}
SEVERITY_ORDER = {"low": 1, "medium": 2, "high": 3, "critical": 4}
MAX_DIFF_CHARS = 60_000


def run_specialist_reviews(*, financial_files, diff_by_file, reviewer):
    assignments = build_specialist_assignments(financial_files)
    if not isinstance(diff_by_file, dict) or set(diff_by_file) - set(financial_files):
        raise ValueError("invalid specialist diff map")
    if not callable(reviewer):
        raise ValueError("reviewer must be callable")
    results = []
    for assignment in assignments:
        role_diff = {}
        for path in assignment["files"]:
            value = diff_by_file.get(path, "")
            if not isinstance(value, str) or len(value) > MAX_DIFF_CHARS:
                raise ValueError("invalid specialist diff")
            role_diff[path] = value
        request = {
            "role": assignment["role"],
            "files": assignment["files"],
            "checks": assignment["checks"],
            "diff_by_file": role_diff,
            "output_requirements": assignment["output_requirements"],
            "merge_authorized": False,
        }
        response = reviewer(request)
        if not isinstance(response, dict) or set(response) != {"verdict", "summary", "findings"}:
            raise ValueError("invalid specialist response")
        if response["verdict"] not in ALLOWED_VERDICTS:
            raise ValueError("invalid specialist verdict")
        if not isinstance(response["summary"], str) or not response["summary"].strip() or len(response["summary"]) > 3000:
            raise ValueError("invalid specialist summary")
        if not isinstance(response["findings"], list) or len(response["findings"]) > 30:
            raise ValueError("invalid specialist findings")
        normalized = []
        for finding in response["findings"]:
            if not isinstance(finding, dict) or set(finding) != {"severity", "path", "explanation"}:
                raise ValueError("invalid specialist finding")
            if finding["severity"] not in SEVERITY_ORDER:
                raise ValueError("invalid specialist severity")
            if finding["path"] not in assignment["files"]:
                raise ValueError("specialist finding references unassigned file")
            if not isinstance(finding["explanation"], str) or not finding["explanation"].strip() or len(finding["explanation"]) > 2000:
                raise ValueError("invalid specialist finding explanation")
            normalized.append(dict(finding))
        results.append({
            "role": assignment["role"],
            "verdict": response["verdict"],
            "summary": response["summary"],
            "findings": normalized,
            "source": "untrusted_specialist_output",
            "trusted": False,
        })
    verdicts = [item["verdict"] for item in results]
    findings = [finding for item in results for finding in item["findings"]]
    if any(item in ("request_changes", "uncertain") for item in verdicts):
        overall = "request_changes" if "request_changes" in verdicts else "uncertain"
    elif any(f["severity"] in ("high", "critical") for f in findings):
        overall = "request_changes"
    else:
        overall = "approve"
    return {
        "specialist_reviews": results,
        "overall_verdict": overall,
        "conflicts_present": len(set(verdicts)) > 1,
        "merge_authorized": False,
        "review_advisory_only": True,
    }
