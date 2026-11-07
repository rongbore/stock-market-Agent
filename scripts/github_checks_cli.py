"""Read-only CLI for GitHub workflow evidence; never prints credentials.

Run only in a trusted environment with a read-only Actions token.
"""
import argparse
import json
import os
import sys

from scripts.final_review_gate import REQUIRED_CHECKS
from scripts.github_workflow_fetch import fetch_workflow_evidence


def main(argv=None):
    parser = argparse.ArgumentParser(description="Read-only GitHub CI evidence fetch")
    parser.add_argument("--repo", required=True)
    parser.add_argument("--head-sha", required=True)
    args = parser.parse_args(argv)
    token = os.environ.get("GITHUB_TOKEN", "")
    try:
        checks = fetch_workflow_evidence(
            args.repo, args.head_sha, REQUIRED_CHECKS, token=token
        )
    except (ValueError, OSError, TimeoutError, json.JSONDecodeError):
        # Do not leak tokens, HTTP headers or response bodies in error messages.
        print(json.dumps({"status": "BLOCKED", "reason": "workflow_evidence_unavailable",
                          "merge_authorized": False}))
        return 1
    print(json.dumps({"status": "VERIFIED_API_RESPONSE", "head_sha": args.head_sha,
                      "checks": checks, "merge_authorized": False},
                     sort_keys=True))
    return 0


if __name__ == "__main__":
    sys.exit(main())
