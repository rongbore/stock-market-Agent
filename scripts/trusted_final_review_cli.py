"""Read-only final advisory gate using live GitHub workflow evidence.

Risk and AI review input are not authenticated here; never authorizes merges.
"""
import argparse
import json
import os
import sys

from scripts.final_review_gate import evaluate, REQUIRED_CHECKS
from scripts.github_workflow_fetch import fetch_workflow_runs
from scripts.github_check_evidence import normalize_workflow_runs


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo", required=True)
    parser.add_argument("--head-sha", required=True)
    parser.add_argument("--evidence-json", required=True)
    args = parser.parse_args(argv)
    try:
        with open(args.evidence_json, encoding="utf-8") as stream:
            evidence = json.load(stream)
        if not isinstance(evidence, dict) or evidence.get("head_sha") != args.head_sha:
            raise ValueError("stale_evidence")
        runs = fetch_workflow_runs(args.repo, args.head_sha,
                                   token=os.environ.get("GITHUB_TOKEN", ""))
        checks = normalize_workflow_runs(runs, args.head_sha, REQUIRED_CHECKS)
        result = evaluate(head_sha=args.head_sha, risk=evidence["risk"],
                          ai_review=evidence["ai_review"], checks=checks,
                          is_draft=evidence["is_draft"],
                          changed_paths=evidence["changed_paths"],
                          workflow_runs=runs, require_workflow_evidence=True)
    except (OSError, ValueError, TypeError, KeyError, TimeoutError):
        result = {"decision": "BLOCKED", "reasons": ["unavailable_or_invalid_evidence"],
                  "merge_authorized": False}
    print(json.dumps(result, sort_keys=True))
    return 0 if result["decision"] == "ELIGIBLE_FOR_POLICY_REVIEW" else 1


if __name__ == "__main__":
    sys.exit(main())
