"""Fail-closed file-change classifier for future low-risk PR automation.

Only standalone documentation files are eligible. This does not grant merge rights.
"""
import json
import sys
from pathlib import PurePosixPath

MAX_FILES = 20
MAX_CHANGED_LINES = 300


def classify(files):
    if not isinstance(files, list) or not 0 < len(files) <= MAX_FILES:
        return "manual", "invalid or oversized file list"
    changed = 0
    for item in files:
        if not isinstance(item, dict):
            return "manual", "invalid file metadata"
        path, status = item.get("filename"), item.get("status")
        additions, deletions = item.get("additions"), item.get("deletions")
        if not isinstance(path, str) or not path or "\\" in path:
            return "manual", "invalid path"
        parts = PurePosixPath(path).parts
        if (path.startswith("/") or "//" in path or any(ord(ch) < 32 or ord(ch) == 127 for ch in path)
                or ".." in parts or any(part.startswith(".") for part in parts)):
            return "manual", "unsafe or ambiguous path"
        if any(part in ("", ".", "..") for part in path.split("/")):
            return "manual", "hidden or traversal path"
        if status not in ("added", "modified"):
            return "manual", "deletion, rename or unknown status"
        if not (path.startswith("docs/") and path.endswith(".md") and len(parts) >= 2):
            return "manual", "not allowlisted documentation"
        if any(type(n) is not int or n < 0 for n in (additions, deletions)):
            return "manual", "invalid diff size"
        changed += additions + deletions
        if changed > MAX_CHANGED_LINES:
            return "manual", "change size exceeds limit"
    return "eligible", "documentation-only candidate; CI and protection still required"


def main():
    data = json.load(sys.stdin)
    decision, reason = classify(data)
    print(json.dumps({"decision": decision, "reason": reason}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
