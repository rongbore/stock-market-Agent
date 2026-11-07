"""Read-only GitHub PR metadata retrieval, with strict identity checks.

No GitHub writes and no merge authorization.
"""
import json
import re
from urllib.request import Request, urlopen

REPO = re.compile(r"^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+$")
SHA = re.compile(r"^[a-f0-9]{40}$")
API = "https://api.github.com"


def _get_json(url, token, opener):
    request = Request(url, headers={
        "Accept": "application/vnd.github+json",
        "Authorization": f"Bearer {token}",
        "X-GitHub-Api-Version": "2022-11-28",
        "User-Agent": "stock-market-agent-pr-evidence",
    })
    with opener(request, timeout=15) as response:
        body = response.read(2_000_001)
    if len(body) > 2_000_000:
        raise ValueError("oversized_api_response")
    return json.loads(body)


def fetch_pr_metadata(repo, number, head_sha, *, token, opener=urlopen):
    if not isinstance(repo, str) or not REPO.fullmatch(repo) or ".." in repo.split("/"):
        raise ValueError("invalid_repository")
    if type(number) is not int or number < 1:
        raise ValueError("invalid_pr_number")
    if not isinstance(head_sha, str) or not SHA.fullmatch(head_sha):
        raise ValueError("invalid_head_sha")
    if not isinstance(token, str) or not token.strip() or "\r" in token or "\n" in token:
        raise ValueError("invalid_token")
    pr = _get_json(f"{API}/repos/{repo}/pulls/{number}", token, opener)
    if not isinstance(pr, dict) or pr.get("number") != number:
        raise ValueError("wrong_pr_number")
    head = pr.get("head")
    if not isinstance(head, dict) or head.get("sha") != head_sha:
        raise ValueError("stale_pr_head")
    base = pr.get("base")
    if not isinstance(base, dict) or base.get("repo", {}).get("full_name") != repo:
        raise ValueError("wrong_base_repository")
    if type(pr.get("draft")) is not bool or pr.get("state") != "open":
        raise ValueError("invalid_pr_state")
    count = pr.get("changed_files")
    if type(count) is not int or count < 1 or count > 100:
        raise ValueError("unsupported_file_count")
    files = _get_json(f"{API}/repos/{repo}/pulls/{number}/files?per_page=100&page=1",
                      token, opener)
    if not isinstance(files, list) or len(files) != count:
        raise ValueError("incomplete_pr_files")
    paths = []
    for item in files:
        if not isinstance(item, dict) or not isinstance(item.get("filename"), str):
            raise ValueError("invalid_changed_file")
        paths.append(item["filename"])
    if len(set(paths)) != len(paths):
        raise ValueError("duplicate_changed_file")
    return {"head_sha": head_sha, "is_draft": pr["draft"],
            "changed_paths": sorted(paths), "pr_number": number,
            "base_repo": repo, "merge_authorized": False}
