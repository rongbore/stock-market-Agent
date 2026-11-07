"""Fail-closed PR preflight: trusted diff collection + allowlist classifier.

No AI model calls or merge operations. Run with exact trusted Git commit SHAs.
"""
import argparse
import json
import sys

from scripts.safe_pr_classifier import classify
from scripts.trusted_pr_diff import collect


def preflight(base_sha, head_sha):
    try:
        changes = collect(base_sha, head_sha)
        decision = classify(changes)
    except (ValueError, OSError, UnicodeError, RuntimeError) as exc:
        # Never print exception details: git errors may contain untrusted paths.
        decision = {"status": "BLOCKED", "reasons": ["diff_collection_failed"]}
    return {
        "status": decision.get("status", "BLOCKED"),
        "reasons": decision.get("reasons", ["missing_decision"]),
        "head_sha": head_sha,
        "review_required": True,
        "merge_authorized": False,
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-sha", required=True)
    parser.add_argument("--head-sha", required=True)
    args = parser.parse_args()
    result = preflight(args.base_sha, args.head_sha)
    print(json.dumps(result, ensure_ascii=False))
    return 0 if result["status"] == "CANDIDATE" else 1


if __name__ == "__main__":
    sys.exit(main())
