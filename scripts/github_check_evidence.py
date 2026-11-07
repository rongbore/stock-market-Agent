"""Normalize GitHub Actions run evidence for advisory review only.

Callers MUST obtain the API response from a trusted authenticated GitHub client.
This parser does not authenticate JSON, call GitHub, or authorize a merge.
"""
import re

SHA = re.compile(r"^[a-f0-9]{40}$")


def normalize_workflow_runs(runs, head_sha, required_names):
    if not isinstance(head_sha, str) or not SHA.fullmatch(head_sha):
        raise ValueError("invalid_head_sha")
    if not isinstance(required_names, (set, frozenset)) or not required_names:
        raise ValueError("invalid_required_names")
    if not isinstance(runs, list) or len(runs) > 500:
        raise ValueError("invalid_runs")
    result = []
    for name in sorted(required_names):
        if not isinstance(name, str) or not name:
            raise ValueError("invalid_name")
        matches = [r for r in runs if isinstance(r, dict)
                   and r.get("name") == name and r.get("head_sha") == head_sha]
        # Duplicate matches can be reruns, but require an explicit attempt/run
        # selection by a trusted caller rather than guessing which is current.
        if len(matches) != 1:
            raise ValueError("missing_or_ambiguous_run:" + name)
        run = matches[0]
        if not isinstance(run.get("id"), int) or isinstance(run["id"], bool) or run["id"] <= 0:
            raise ValueError("invalid_run_id")
        if run.get("event") != "pull_request":
            raise ValueError("untrusted_event")
        if run.get("status") != "completed" or run.get("conclusion") != "success":
            raise ValueError("incomplete_or_failed_run")
        result.append({"name": name, "head_sha": head_sha,
                       "status": "completed", "conclusion": "success"})
    return result
