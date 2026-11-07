"""Read-only GitHub Actions evidence fetcher for trusted integrations.

Uses the official GitHub REST API. Never grants merge permission.
"""
import json
import re
from urllib.request import Request, urlopen

from scripts.github_check_evidence import normalize_workflow_runs

REPO = re.compile(r"^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+$")
SHA = re.compile(r"^[a-f0-9]{40}$")
API = "https://api.github.com"


def fetch_workflow_runs(repo, head_sha, *, token, opener=urlopen):
    if not isinstance(repo, str) or not REPO.fullmatch(repo) or ".." in repo.split("/"):
        raise ValueError("invalid_repository")
    if not isinstance(head_sha, str) or not SHA.fullmatch(head_sha):
        raise ValueError("invalid_head_sha")
    if not isinstance(token, str) or not token.strip() or "\r" in token or "\n" in token:
        raise ValueError("missing_or_invalid_token")
    url = f"{API}/repos/{repo}/actions/runs?head_sha={head_sha}&per_page=100&page=1"
    request = Request(url, headers={
        "Accept": "application/vnd.github+json",
        "Authorization": f"Bearer {token}",
        "X-GitHub-Api-Version": "2022-11-28",
        "User-Agent": "stock-market-agent-review-evidence",
    })
    with opener(request, timeout=15) as response:
        body = response.read(2_000_001)
    if len(body) > 2_000_000:
        raise ValueError("oversized_api_response")
    data = json.loads(body)
    if not isinstance(data, dict) or not isinstance(data.get("workflow_runs"), list):
        raise ValueError("invalid_api_response")
    # Do not silently accept an incomplete first page as exhaustive evidence.
    if type(data.get("total_count")) is not int or data["total_count"] > 100:
        raise ValueError("ambiguous_paginated_results")
    if len(data["workflow_runs"]) != data["total_count"]:
        raise ValueError("incomplete_api_response")
    return data["workflow_runs"]


def fetch_workflow_evidence(repo, head_sha, required_names, *, token, opener=urlopen):
    """Return validated normalized checks for the requested SHA."""
    runs = fetch_workflow_runs(repo, head_sha, token=token, opener=opener)
    return normalize_workflow_runs(runs, head_sha, required_names)
