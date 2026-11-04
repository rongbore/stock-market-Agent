"""Validate human PDF candidate review annotations without verifying financial meaning."""
import re
import math

_SHA256 = re.compile(r"^[0-9a-f]{64}$")
_STATUSES = frozenset(("pending_manual_review", "accepted_by_reviewer", "rejected_by_reviewer"))


def validate_review_annotations(manifest, annotations):
    """Join review decisions to exact SHA/page/bbox; reject stale or ambiguous records."""
    if not isinstance(manifest, dict) or not isinstance(annotations, dict):
        raise ValueError("manifest and annotations must be objects")
    sha = manifest.get("file_sha256")
    if not isinstance(sha, str) or not _SHA256.fullmatch(sha):
        raise ValueError("invalid manifest SHA256")
    if annotations.get("file_sha256") != sha:
        raise ValueError("review file fingerprint mismatch")
    candidates = manifest.get("candidates")
    decisions = annotations.get("decisions")
    if not isinstance(candidates, list) or not isinstance(decisions, list):
        raise ValueError("candidates and decisions must be lists")
    if len(candidates) > 100 or len(decisions) > 100:
        raise ValueError("too many review entries")
    keys = []
    for candidate in candidates:
        if not isinstance(candidate, dict):
            raise ValueError("invalid candidate")
        page, bbox = candidate.get("page"), candidate.get("bbox")
        if type(page) is not int or page < 1 or not isinstance(bbox, list) or len(bbox) != 4:
            raise ValueError("invalid candidate identity")
        if any(type(x) not in (int, float) or not math.isfinite(x) for x in bbox):
            raise ValueError("invalid bbox")
        keys.append((page, tuple(bbox)))
    if len(set(keys)) != len(keys):
        raise ValueError("ambiguous duplicate candidate")
    indexed = set()
    output = []
    for decision in decisions:
        if not isinstance(decision, dict):
            raise ValueError("invalid review decision")
        index = decision.get("candidate_index")
        status = decision.get("review_status")
        reviewer = decision.get("reviewer")
        if type(index) is not int or not 0 <= index < len(candidates) or index in indexed:
            raise ValueError("invalid or duplicate candidate index")
        if status not in _STATUSES:
            raise ValueError("unsupported review status")
        if status != "pending_manual_review" and (
            not isinstance(reviewer, str) or not 1 <= len(reviewer.strip()) <= 100
        ):
            raise ValueError("reviewer required for decision")
        if decision.get("page") != keys[index][0] or decision.get("bbox") != list(keys[index][1]):
            raise ValueError("candidate coordinates changed since review")
        indexed.add(index)
        output.append({
            "candidate_index": index, "page": keys[index][0],
            "bbox": list(keys[index][1]), "review_status": status,
            "reviewer": reviewer if isinstance(reviewer, str) else None,
            "financial_meaning_verified": False,
        })
    return {
        "file_sha256": sha, "review_decisions": output,
        "review_complete": len(indexed) == len(candidates)
        and all(item["review_status"] != "pending_manual_review" for item in output),
        "official_origin_verified": False,
        "financial_meaning_verified": False,
        "note": "Human rectangle review is not verification of financial metrics or filing origin.",
    }
