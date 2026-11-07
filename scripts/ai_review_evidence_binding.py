"""Bind untrusted model review to immutable request evidence (offline).

Caller must authenticate the PR diff and model invocation independently.
No network, model calls, credentials, review submission, or merging.
"""
import hashlib
import json
import re

from scripts.ai_review_provider_adapter import build_request, parse_review

_SHA = re.compile(r"^[0-9a-f]{40}$")


def _digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=False,
                                     separators=(",", ":")).encode("utf-8")).hexdigest()


def prepare_review(*, head_sha, changed_files, diff, financial_context=None):
    request = build_request(head_sha=head_sha, changed_files=changed_files, diff=diff,
                            financial_context=financial_context)
    return {"request": request, "request_digest": _digest(request),
            "head_sha": head_sha, "review_only": True}


def attach_review(*, prepared, response, expected_head_sha, expected_digest):
    if not isinstance(prepared, dict) or not isinstance(expected_head_sha, str) or not _SHA.fullmatch(expected_head_sha):
        raise ValueError("invalid review context")
    if not isinstance(expected_digest, str) or not re.fullmatch(r"[0-9a-f]{64}", expected_digest):
        raise ValueError("invalid expected digest")
    request = prepared.get("request")
    if not isinstance(request, dict) or request.get("head_sha") != expected_head_sha:
        raise ValueError("head SHA mismatch")
    if prepared.get("head_sha") != expected_head_sha:
        raise ValueError("prepared SHA mismatch")
    actual = _digest(request)
    if actual != expected_digest or prepared.get("request_digest") != actual:
        raise ValueError("review request changed")
    review = parse_review(response, head_sha=expected_head_sha)
    return {"head_sha": expected_head_sha, "request_digest": actual,
            "review": review, "status": "ADVISORY_ONLY",
            "evidence_authenticated": False, "merge_authorized": False}
