"""Manually triggered, read-only PR review using trusted GitHub REST metadata.

Runs from default-branch workflow, never checks out PR code or grants merge.
"""
import argparse
import json
import os
import sys
import urllib.error
import urllib.request

from scripts.ai_review_evidence_binding import prepare_review
from scripts.ai_review_http_client import invoke_review


def github_json(path, token):
    request = urllib.request.Request(
        "https://api.github.com/repos/" + path,
        headers={"Authorization": "Bearer " + token,
                 "Accept": "application/vnd.github+json",
                 "User-Agent": "stock-market-agent-readonly-review"},
    )
    with urllib.request.urlopen(request, timeout=20) as response:
        return json.load(response)


def run(*, repo, pr_number, github_token, model_token, endpoint, model):
    if repo != "rongbore/stock-market-Agent" or type(pr_number) is not int or pr_number <= 0:
        raise ValueError("unsupported repository or PR")
    if not github_token or not model_token:
        raise ValueError("required token missing")
    prefix = repo + "/"
    pr = github_json(prefix + "pulls/" + str(pr_number), github_token)
    if pr.get("state") != "open" or pr.get("base", {}).get("ref") != "main":
        raise ValueError("PR not open against main")
    sha = pr["head"]["sha"]
    files = []
    for page in range(1, 5):
        batch = github_json(prefix + "pulls/" + str(pr_number) + "/files?per_page=100&page=" + str(page), github_token)
        if not isinstance(batch, list):
            raise ValueError("invalid file listing")
        files.extend(batch)
        if len(batch) < 100:
            break
    if not files or len(files) > 30 or len(batch) == 100:
        raise ValueError("file listing too large or incomplete")
    if any(f.get("status") not in ("added", "modified") or not isinstance(f.get("patch"), str) for f in files):
        raise ValueError("binary, deleted, renamed or missing patch")
    changed_files = [f["filename"] for f in files]
    diff = "\n".join("FILE " + f["filename"] + "\n" + f["patch"] for f in files)
    prepared = prepare_review(head_sha=sha, changed_files=changed_files, diff=diff)
    result = invoke_review(prepared=prepared, expected_head_sha=sha,
                           expected_digest=prepared["request_digest"], endpoint=endpoint,
                           token=model_token, model=model)
    latest = github_json(prefix + "pulls/" + str(pr_number), github_token)
    if latest["head"]["sha"] != sha or latest.get("state") != "open":
        raise ValueError("PR changed during review")
    return {"pr_number": pr_number, "head_sha": sha,
            "verdict": result["review"]["verdict"],
            "findings": result["review"]["findings"],
            "summary": result["review"]["summary"],
            "merge_authorized": False, "review_advisory_only": True}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--pr-number", type=int, required=True)
    args = parser.parse_args()
    try:
        result = run(repo=os.environ.get("GITHUB_REPOSITORY", ""),
                     pr_number=args.pr_number,
                     github_token=os.environ.get("GITHUB_TOKEN", ""),
                     model_token=os.environ.get("AI_REVIEW_API_KEY", ""),
                     endpoint=os.environ.get("AI_REVIEW_ENDPOINT", ""),
                     model=os.environ.get("AI_REVIEW_MODEL", ""))
        print(json.dumps(result, ensure_ascii=False))
        return 0
    except (ValueError, KeyError, TypeError, OSError, urllib.error.URLError):
        print(json.dumps({"status": "BLOCKED", "reason": "review_unavailable_or_invalid",
                          "merge_authorized": False}))
        return 1


if __name__ == "__main__":
    sys.exit(main())
