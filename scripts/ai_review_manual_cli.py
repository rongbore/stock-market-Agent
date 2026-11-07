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
from scripts.financial_ai_review_rules import assess_financial_pr
from scripts.financial_ai_review_context import build_financial_review_context
from scripts.financial_ai_review_provider import review_financial_changes_with_roundtable


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
    if pr.get("state") != "open":
        raise ValueError("PR is not open")
    # Allow stacked PRs targeting another branch in this same repository.
    # Never send fork PR diffs to the external model provider.
    base_repo = pr.get("base", {}).get("repo", {}).get("full_name")
    head_repo = pr.get("head", {}).get("repo", {}).get("full_name")
    if base_repo != repo or head_repo != repo:
        raise ValueError("PR must belong to the trusted repository")
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
    # Deterministic finance-domain preflight; model output remains advisory.
    per_file_diffs = {item["filename"]: item["patch"] for item in files}
    preflight = assess_financial_pr(changed_files, per_file_diffs)
    financial_context = build_financial_review_context(preflight)
    allowed_hosts = [
        host.strip()
        for host in os.environ.get("AI_REVIEW_ALLOWED_HOSTS", "").split(",")
        if host.strip()
    ]

    # Sensitive/security changes retain the existing single read-only review path.
    # Ordinary financial changes use five independent specialists, bounded group
    # discussion and a moderator; non-financial files in a mixed PR get a separate
    # generic pass so they are not silently omitted.
    if preflight["financial_files"] and not preflight["sensitive_files"]:
        financial_files = preflight["financial_files"]
        financial_diffs = {path: per_file_diffs[path] for path in financial_files}
        rounds = int(os.environ.get("AI_REVIEW_ROUNDTABLE_ROUNDS", "2"))
        roundtable = review_financial_changes_with_roundtable(
            head_sha=sha,
            financial_files=financial_files,
            diff_by_file=financial_diffs,
            endpoint=endpoint,
            token=model_token,
            model=model,
            allowed_hosts=allowed_hosts,
            rounds=rounds,
        )
        generic_result = None
        nonfinancial_files = [
            path for path in changed_files if path not in set(financial_files)
        ]
        if nonfinancial_files:
            generic_diff = "\n".join(
                "FILE " + item["filename"] + "\n" + item["patch"]
                for item in files if item["filename"] in set(nonfinancial_files)
            )
            generic_prepared = prepare_review(
                head_sha=sha, changed_files=nonfinancial_files, diff=generic_diff
            )
            generic_result = invoke_review(
                prepared=generic_prepared,
                expected_head_sha=sha,
                expected_digest=generic_prepared["request_digest"],
                endpoint=endpoint,
                token=model_token,
                model=model,
                allowed_hosts=allowed_hosts,
            )["review"]

        all_findings = []
        for review in roundtable["independent_reviews"]:
            all_findings.extend(review["findings"])
        for turn in roundtable["discussion_transcript"]:
            all_findings.extend(turn["findings"])
        for review in roundtable["specialist_final_positions"]:
            all_findings.extend(review["findings"])
        moderator = roundtable["moderator_synthesis"]
        if moderator:
            all_findings.extend(moderator["findings"])
        if generic_result:
            all_findings.extend(generic_result["findings"])
        unique_findings = []
        seen_findings = set()
        for finding in all_findings:
            key = json.dumps(finding, ensure_ascii=False, sort_keys=True)
            if key not in seen_findings:
                seen_findings.add(key)
                unique_findings.append(finding)

        verdicts = [roundtable["overall_verdict"]]
        if generic_result:
            verdicts.append(generic_result["verdict"])
        if "request_changes" in verdicts:
            overall_verdict = "request_changes"
        elif "uncertain" in verdicts:
            overall_verdict = "uncertain"
        else:
            overall_verdict = "approve"
        summaries = []
        if moderator:
            summaries.append("五 Agent 讨论结论：" + moderator["summary"])
        if generic_result:
            summaries.append("非金融文件审核：" + generic_result["summary"])
        review_output = {
            "pr_number": pr_number,
            "head_sha": sha,
            "verdict": overall_verdict,
            "summary": "\n\n".join(summaries),
            "findings": unique_findings,
            "financial_roundtable": roundtable,
            "generic_review": generic_result,
            "model_calls": 5 + 5 * rounds + 1 + (1 if generic_result else 0),
            "merge_authorized": False,
            "review_advisory_only": True,
        }
    else:
        prepared = prepare_review(head_sha=sha, changed_files=changed_files, diff=diff,
                                  financial_context=financial_context)
        result = invoke_review(prepared=prepared, expected_head_sha=sha,
                               expected_digest=prepared["request_digest"], endpoint=endpoint,
                               token=model_token, model=model,
                               allowed_hosts=allowed_hosts)
        review_output = {
            "pr_number": pr_number, "head_sha": sha,
            "verdict": result["review"]["verdict"],
            "findings": result["review"]["findings"],
            "summary": result["review"]["summary"],
            "model_calls": 1,
            "merge_authorized": False, "review_advisory_only": True,
        }

    latest = github_json(prefix + "pulls/" + str(pr_number), github_token)
    if latest["head"]["sha"] != sha or latest.get("state") != "open":
        raise ValueError("PR changed during review")
    return review_output


def _write_json_output(path, payload):
    rendered = json.dumps(payload, ensure_ascii=False, indent=2) + "\n"
    with open(path, "w", encoding="utf-8") as output:
        output.write(rendered)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--pr-number", type=int, required=True)
    parser.add_argument("--output", default="ai-review-result.json")
    args = parser.parse_args()
    try:
        result = run(repo=os.environ.get("GITHUB_REPOSITORY", ""),
                     pr_number=args.pr_number,
                     github_token=os.environ.get("GITHUB_TOKEN", ""),
                     model_token=os.environ.get("AI_REVIEW_API_KEY", ""),
                     endpoint=os.environ.get("AI_REVIEW_ENDPOINT", ""),
                     model=os.environ.get("AI_REVIEW_MODEL", ""))
        _write_json_output(args.output, result)
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0
    except ValueError as exc:
        # ValueError messages from the transport are fixed diagnostic codes, not raw provider text.
        code = str(exc)
        allowed = {"provider_http_400", "provider_http_401", "provider_http_402", "provider_http_403",
                   "provider_http_404", "provider_http_408", "provider_http_429", "provider_http_500",
                   "provider_http_502", "provider_http_503", "provider_timeout", "provider_network_error",
                   "invalid provider response", "invalid review", "review is not JSON",
                   "review request changed", "stale or modified request", "invalid endpoint",
                   "HTTPS endpoint without credentials or fragment required", "missing API credential",
                   "invalid model", "invalid or oversized diff", "provider host allowlist required",
                   "provider host not allowlisted", "IP literal endpoints forbidden",
                   "endpoint query and nonstandard ports forbidden", "file listing too large or incomplete",
                   "binary, deleted, renamed or missing patch", "PR changed during review",
                   "PR is not open", "PR must belong to the trusted repository", "required token missing", "unsupported repository or PR"}
        reason = code if code in allowed else "review_validation_failed"
        blocked = {"status": "BLOCKED", "reason": reason, "merge_authorized": False}
        _write_json_output(args.output, blocked)
        print(json.dumps(blocked, ensure_ascii=False))
        return 1
    except (KeyError, TypeError, OSError, urllib.error.URLError):
        blocked = {"status": "BLOCKED", "reason": "review_internal_or_network_error",
                   "merge_authorized": False}
        _write_json_output(args.output, blocked)
        print(json.dumps(blocked, ensure_ascii=False))
        return 1


if __name__ == "__main__":
    sys.exit(main())
