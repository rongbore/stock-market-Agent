"""Read-only PR review diagnostic. No merge, approvals or repository writes."""
import json
import os
import subprocess
import sys

from scripts.trusted_review_check import check


def api(path):
    result = subprocess.run(["gh", "api", path], capture_output=True, text=True, check=True)
    return json.loads(result.stdout)


def api_paginated(path):
    result = subprocess.run(["gh", "api", "--paginate", "--slurp", path], capture_output=True, text=True, check=True)
    pages = json.loads(result.stdout)
    if not isinstance(pages, list) or any(not isinstance(page, list) for page in pages):
        raise ValueError("unexpected paginated response")
    return [item for page in pages for item in page]


def run(repo, number):
    pr = api(f"repos/{repo}/pulls/{number}")
    files = api_paginated(f"repos/{repo}/pulls/{number}/files?per_page=100")
    reviews = api_paginated(f"repos/{repo}/pulls/{number}/reviews?per_page=100")
    if not isinstance(pr, dict) or not isinstance(files, list) or not isinstance(reviews, list):
        raise ValueError("invalid API payload")
    trusted = []
    for login in {(r.get("user") or {}).get("login") for r in reviews if isinstance(r, dict)}:
        if not isinstance(login, str):
            continue
        try:
            permission = api(f"repos/{repo}/collaborators/{login}/permission")
        except subprocess.CalledProcessError:
            continue
        if isinstance(permission, dict) and permission.get("permission") in ("admin", "maintain", "write"):
            trusted.append(login)
    decision, reason = check(
        {"changed_files": pr.get("changed_files"),
         "head_sha": pr.get("head", {}).get("sha"),
         "author": pr.get("user", {}).get("login")},
        files,
        [{"user": r.get("user", {}).get("login"),
          "state": r.get("state"),
          "submitted_at": r.get("submitted_at"),
          "commit_id": r.get("commit_id")} for r in reviews],
        trusted,
    )
    latest = api(f"repos/{repo}/pulls/{number}")
    if latest.get("head", {}).get("sha") != pr.get("head", {}).get("sha"):
        return False, "head changed during review verification"
    return decision, reason


def main():
    try:
        repo = os.environ["GH_REPO"]
        number = int(os.environ["PR_NUMBER"])
        if not repo or number < 1:
            raise ValueError("invalid PR identity")
        decision, reason = run(repo, number)
    except (KeyError, ValueError, TypeError, subprocess.CalledProcessError) as exc:
        decision, reason = False, "unable to verify review metadata"
    print(json.dumps({"eligible": decision, "reason": reason}))
    # Diagnostic intentionally succeeds regardless of policy decision:
    # never make this job a required status check.
    return 0


if __name__ == "__main__":
    sys.exit(main())
