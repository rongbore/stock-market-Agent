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
from scripts.github_pr_metadata import fetch_pr_metadata


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo", required=True)
    parser.add_argument("--head-sha", required=True)
    parser.add_argument("--pr-number", type=int, required=True)
    parser.add_argument("--evidence-json", required=True)
    args = parser.parse_args(argv)
    try:
        with open(args.evidence_json, encoding="utf-8") as stream:
            evidence = json.load(stream)
        if not isinstance(evidence, dict) or evidence.get("head_sha") != args.head_sha:
            raise ValueError("stale_evidence")
        token = os.environ.get("GITHUB_TOKEN", "")
        pr_before = fetch_pr_metadata(args.repo, args.pr_number, args.head_sha,
                                      token=token)
        runs = fetch_workflow_runs(args.repo, args.head_sha,
                                   token=token)
        checks = normalize_workflow_runs(runs, args.head_sha, REQUIRED_CHECKS)
        result = evaluate(head_sha=args.head_sha, risk=evidence["risk"],
                          ai_review=evidence["ai_review"], checks=checks,
                          is_draft=pr_before["is_draft"],
                          changed_paths=pr_before["changed_paths"],
                          workflow_runs=runs, require_workflow_evidence=True)
        pr_after = fetch_pr_metadata(args.repo, args.pr_number, args.head_sha,
                                     token=token)
        if pr_before != pr_after:
            raise ValueError("pr_changed_during_review")
    except (OSError, ValueError, TypeError, KeyError, TimeoutError):
        result = {"decision": "BLOCKED", "reasons": ["unavailable_or_invalid_evidence"],
                  "merge_authorized": False}
    print(json.dumps(result, sort_keys=True))
    return 0 if result["decision"] == "ELIGIBLE_FOR_POLICY_REVIEW" else 1


if __name__ == "__main__":
    sys.exit(main())
