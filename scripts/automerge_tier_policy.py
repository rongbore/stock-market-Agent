"""Fail-closed, offline policy for staged AI-assisted merge eligibility.

Classification is advisory. No AI result or this module grants merge rights.
"""
MAX_FILES = 20
MAX_CHANGED_LINES = 300
DOC_PREFIX = "docs/"


def classify_tier(files, *, expected_count=None):
    def blocked(reason):
        return {"tier": "manual", "reason": reason, "auto_merge_authorized": False}
    if not isinstance(files, list) or not files or len(files) > MAX_FILES:
        return blocked("invalid_or_oversized_file_list")
    if type(expected_count) is not int or expected_count != len(files):
        return blocked("incomplete_changed_file_evidence")
    paths, changed = [], 0
    for item in files:
        if not isinstance(item, dict):
            return blocked("invalid_file_metadata")
        path = item.get("filename")
        if not isinstance(path, str) or not path or "\\" in path or path.startswith("/"):
            return blocked("unsafe_path")
        parts = path.split("/")
        if any(not p or p in (".", "..") or p.startswith(".") for p in parts):
            return blocked("unsafe_path")
        if any(ord(c) < 32 or ord(c) > 126 for c in path):
            return blocked("unsafe_path")
        if item.get("status") not in ("added", "modified") or item.get("previous_filename") is not None:
            return blocked("rename_or_delete")
        a, d = item.get("additions"), item.get("deletions")
        if type(a) is not int or type(d) is not int or min(a, d) < 0:
            return blocked("invalid_diff_counts")
        changed += a + d
        if changed > MAX_CHANGED_LINES:
            return blocked("oversized_diff")
        paths.append(path)
    if len(set(paths)) != len(paths):
        return blocked("duplicate_paths")
    if all(p.startswith(DOC_PREFIX) and p.endswith(".md") for p in paths):
        tier = "documentation_candidate"
    else:
        return blocked("non_documentation_changes_require_manual_review")
    return {
        "tier": tier,
        "reason": "candidate_only_requires_trusted_review_and_ci",
        "auto_merge_authorized": False,
    }
