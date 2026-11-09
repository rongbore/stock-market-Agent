"""Record reviewer assertions bound to an exact, unverified table review package."""
import copy
import hashlib
import json
import re


def review_package_sha256(package):
    """Fingerprint canonical package JSON; this does not authenticate its origin."""
    if not isinstance(package, dict) or package.get("schema_version") != "0.1":
        raise ValueError("unsupported review package")
    if package.get("status") != "PENDING_MANUAL_VERIFICATION":
        raise ValueError("package must remain pending verification")
    digest = package.get("file_sha256")
    if not isinstance(digest, str) or not re.fullmatch(r"[0-9a-f]{64}", digest):
        raise ValueError("invalid PDF fingerprint")
    candidates = package.get("candidates")
    if not isinstance(candidates, list) or len(candidates) > 20000:
        raise ValueError("invalid candidate list")
    if type(package.get("candidate_count")) is not int or package["candidate_count"] != len(candidates):
        raise ValueError("candidate count mismatch")

    def check_flags(value):
        if isinstance(value, dict):
            for key, item in value.items():
                if not isinstance(key, str):
                    raise ValueError("package JSON keys must be strings")
                if key.endswith("_verified") and item is not False:
                    raise ValueError("unsupported verification assertion")
                check_flags(item)
        elif isinstance(value, list):
            for item in value:
                check_flags(item)

    try:
        check_flags(package)
        raw = json.dumps(package, sort_keys=True, separators=(",", ":"),
                         ensure_ascii=False, allow_nan=False).encode("utf-8")
    except (TypeError, RecursionError) as exc:
        raise ValueError("invalid package JSON") from exc
    if len(raw) > 5 * 1024 * 1024:
        raise ValueError("review package too large")
    return hashlib.sha256(raw).hexdigest()


def record_table_reviews(package, annotations):
    """Validate asserted decisions; retain original blockers and verification flags."""
    digest = review_package_sha256(package)
    if not isinstance(annotations, dict) or set(annotations) != {
            "file_sha256", "package_sha256", "decisions"}:
        raise ValueError("invalid annotation fields")
    if annotations["package_sha256"] != digest or annotations["file_sha256"] != package["file_sha256"]:
        raise ValueError("review fingerprint mismatch")
    decisions = annotations["decisions"]
    if not isinstance(decisions, list) or len(decisions) > len(package["candidates"]):
        raise ValueError("invalid decisions")
    indexed = {}
    for decision in decisions:
        if not isinstance(decision, dict) or set(decision) != {
                "candidate_index", "decision", "reviewer", "note"}:
            raise ValueError("invalid decision fields")
        index = decision["candidate_index"]
        if type(index) is not int or not 0 <= index < len(package["candidates"]) or index in indexed:
            raise ValueError("invalid or duplicate candidate index")
        if decision["decision"] not in ("accepted_by_reviewer", "rejected_by_reviewer"):
            raise ValueError("unsupported decision")
        for key, limit in (("reviewer", 100), ("note", 2000)):
            if not isinstance(decision[key], str) or not 1 <= len(decision[key].strip()) <= limit:
                raise ValueError(f"nonempty {key} required")
        indexed[index] = copy.deepcopy(decision)
    rows = [{"candidate_index": index, "decision": "pending_manual_review"}
            if index not in indexed else indexed[index]
            for index in range(len(package["candidates"]))]
    return {"schema_version": "0.1", "file_sha256": package["file_sha256"],
            "package_sha256": digest, "status": "REVIEW_ASSERTIONS_RECORDED_UNVERIFIED",
            "package": copy.deepcopy(package), "decisions": rows,
            "decided_count": len(indexed), "pending_count": len(rows) - len(indexed),
            "all_candidates_decided": bool(rows) and len(indexed) == len(rows),
            "reviewer_identity_verified": False, "financial_meaning_verified": False,
            "release_evidence_accepted": False}
