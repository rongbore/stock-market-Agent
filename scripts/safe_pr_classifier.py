"""Fail-closed classification of proposed PR file changes.

This module does not authorize merges, call models, or read credentials.
The caller must supply complete, trusted GitHub changed-file metadata.
"""
import argparse
import json
import re
from pathlib import PurePosixPath

MAX_FILES = 50
MAX_PATCH_BYTES = 150_000
DOC_PATH = re.compile(r"^docs/(?:[A-Za-z0-9_-]+/)*[A-Za-z0-9_-]+\.md$")
FORBIDDEN_TEXT = re.compile(
    r"(?i)(?:-----BEGIN [A-Z ]*PRIVATE KEY-----|"
    r"gh[pousr]_[A-Za-z0-9_]{20,}|"
    r"github_pat_[A-Za-z0-9_]{20,}|"
    r"AKIA[0-9A-Z]{16}|"
    r"(?:(?:api[_-]?key|secret|token|password)\s*[:=]\s*['\"][^'\"]{8,}))"
)
# Markdown can carry active HTML or workflow instructions; exclude it from auto-merge.
ACTIVE_CONTENT = re.compile(
    r"(?i)(<\s*(?:script|iframe|object|embed|form|meta|link)\b|"
    r"javascript\s*:|data\s*:\s*text/html|"
    r"on(?:load|error|click|mouseover)\s*=|"
    r"\b(?:curl|wget)\s+[^\n]*\|\s*(?:sh|bash)\b)"
)


def classify(changes):
    """Return an advisory result, never a merge authorization."""
    reasons = []
    if not isinstance(changes, list) or not 1 <= len(changes) <= MAX_FILES:
        return {"status": "BLOCKED", "reasons": ["invalid_or_incomplete_change_list"]}
    for i, item in enumerate(changes):
        if not isinstance(item, dict):
            reasons.append(f"file_{i}:invalid_metadata")
            continue
        path = item.get("filename")
        if not isinstance(path, str) or not DOC_PATH.fullmatch(path):
            reasons.append(f"file_{i}:not_allowlisted")
            continue
        if PurePosixPath(path).is_absolute() or ".." in PurePosixPath(path).parts:
            reasons.append(f"file_{i}:unsafe_path")
        # Only newly added or modified regular files. Renames/copies/deletions blocked.
        if item.get("status") not in ("added", "modified"):
            reasons.append(f"file_{i}:unsupported_status")
        if item.get("type") != "file" or item.get("mode") not in ("100644", 33188):
            reasons.append(f"file_{i}:unverified_regular_file_mode")
        if item.get("binary") is not False:
            reasons.append(f"file_{i}:binary_or_unknown")
        patch = item.get("patch")
        if not isinstance(patch, str) or len(patch.encode("utf-8")) > MAX_PATCH_BYTES:
            reasons.append(f"file_{i}:missing_or_oversized_patch")
            continue
        added_lines = "\n".join(
            line[1:] for line in patch.splitlines()
            if line.startswith("+") and not line.startswith("+++")
        )
        if FORBIDDEN_TEXT.search(added_lines):
            reasons.append(f"file_{i}:possible_secret")
        if ACTIVE_CONTENT.search(added_lines):
            reasons.append(f"file_{i}:active_content")
    return {
        "status": "CANDIDATE" if not reasons else "BLOCKED",
        "reasons": reasons,
        "advisory_only": True,
        "requires_ci_and_ai_review": True,
        "auto_merge_enabled": False,
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("changes_json", help="Trusted complete changed-file metadata JSON")
    args = parser.parse_args()
    try:
        with open(args.changes_json, encoding="utf-8") as handle:
            data = json.load(handle)
        result = classify(data)
    except (OSError, ValueError, UnicodeError):
        result = {"status": "BLOCKED", "reasons": ["unreadable_change_metadata"]}
    print(json.dumps(result, ensure_ascii=False))
    raise SystemExit(0 if result["status"] == "CANDIDATE" else 1)


if __name__ == "__main__":
    main()
