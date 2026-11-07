"""Opt-in provider-backed dispatcher for independent finance specialist reviews.

Each role gets a separate bounded request and model response. The caller must
explicitly supply credentials and an exact HTTPS host allowlist. Results remain
untrusted/advisory and cannot authorize merges or trading.
"""
import json

from scripts.ai_review_evidence_binding import prepare_review
from scripts.ai_review_http_client import invoke_review
from scripts.financial_ai_review_orchestrator import run_specialist_reviews

MAX_CONTEXT = 12_000


def make_provider_reviewer(*, head_sha, endpoint, token, model, allowed_hosts,
                           timeout=60, invoke=invoke_review):
    if not isinstance(allowed_hosts, (list, tuple, set)) or not allowed_hosts:
        raise ValueError("provider host allowlist required")

    def reviewer(task):
        role = task.get("role")
        files = task.get("files")
        diff_by_file = task.get("diff_by_file")
        if not isinstance(role, str) or not isinstance(files, list) or not files:
            raise ValueError("invalid specialist task")
        if not isinstance(diff_by_file, dict) or set(diff_by_file) != set(files):
            raise ValueError("invalid specialist diff map")
        diff = "\n".join("FILE " + path + "\n" + diff_by_file[path] for path in files)
        context = {
            "schema_version": "1.0",
            "scope": "financial_domain_review",
            "role": role,
            "required_checks": task.get("checks", []),
            "output_requirements": task.get("output_requirements", []),
            "merge_authorized": False,
            "ai_review_is_advisory": True,
        }
        rendered = json.dumps(context, ensure_ascii=False, sort_keys=True)
        if len(rendered) > MAX_CONTEXT:
            raise ValueError("financial review context exceeds size limit")
        prepared = prepare_review(head_sha=head_sha, changed_files=files,
                                  diff=diff, financial_context=rendered)
        result = invoke(
            prepared=prepared,
            expected_head_sha=head_sha,
            expected_digest=prepared["request_digest"],
            endpoint=endpoint,
            token=token,
            model=model,
            timeout=timeout,
            allowed_hosts=allowed_hosts,
        )
        review = result.get("review", {})
        if result.get("merge_authorized") is not False or result.get("status") != "ADVISORY_ONLY":
            raise ValueError("invalid advisory review result")
        return {
            "verdict": review.get("verdict"),
            "summary": review.get("summary"),
            "findings": review.get("findings"),
        }

    return reviewer



def review_financial_changes(*, head_sha, financial_files, diff_by_file,
                             endpoint, token, model, allowed_hosts,
                             timeout=60, invoke=invoke_review):
    """Run each matched specialist as a separate provider call and aggregate."""
    reviewer = make_provider_reviewer(
        head_sha=head_sha, endpoint=endpoint, token=token, model=model,
        allowed_hosts=allowed_hosts, timeout=timeout, invoke=invoke)
    return run_specialist_reviews(
        financial_files=financial_files,
        diff_by_file=diff_by_file,
        reviewer=reviewer,
    )
