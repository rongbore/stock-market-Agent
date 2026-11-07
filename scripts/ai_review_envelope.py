"""Build a bounded, deterministic review request without sending source code.

This is an audit envelope for a future AI reviewer, not an AI review itself.
"""
import argparse
import hashlib
import json
import re

from scripts.safe_pr_classifier import classify, DOC_PATH

SHA = re.compile(r"^[a-f0-9]{40}$")
MAX_FILES = 50
MAX_FILE_BYTES = 150_000
MAX_TOTAL_BYTES = 300_000


def build_envelope(changes, head_sha, base_sha):
    if not all(isinstance(s, str) and SHA.fullmatch(s) for s in (head_sha, base_sha)):
        raise ValueError("invalid_sha")
    if not isinstance(changes, list) or not 1 <= len(changes) <= MAX_FILES:
        raise ValueError("invalid_change_list")
    # The request envelope must never label an unsafe document as a candidate.
    # Reuse the same complete-content scanner as the PR risk gate.
    if classify(changes).get("status") != "CANDIDATE":
        raise ValueError("unsafe_change_list")
    total = 0
    files = []
    seen = set()
    for item in changes:
        if not isinstance(item, dict):
            raise ValueError("invalid_file")
        path = item.get("filename")
        patch = item.get("patch")
        if not isinstance(path, str) or not DOC_PATH.fullmatch(path) or len(path) > 256 or path in seen:
            raise ValueError("unsafe_or_duplicate_path")
        if any(ord(c) < 32 or ord(c) == 127 for c in path) or ".." in path.split("/"):
            raise ValueError("unsafe_path")
        if item.get("status") not in ("added", "modified") or item.get("type") != "file" or item.get("mode") != "100644" or item.get("binary") is not False:
            raise ValueError("untrusted_metadata")
        if not isinstance(patch, str):
            raise ValueError("missing_patch")
        raw = patch.encode("utf-8")
        total += len(raw)
        if len(raw) > MAX_FILE_BYTES or total > MAX_TOTAL_BYTES:
            raise ValueError("oversized_review")
        seen.add(path)
        files.append({"path": path, "status": item["status"], "bytes": len(raw),
                      "sha256": hashlib.sha256(raw).hexdigest()})
    files.sort(key=lambda x: x["path"])
    return {"schema_version": "1", "head_sha": head_sha, "base_sha": base_sha,
            "file_count": len(files), "files": files, "source_code_included": False,
            "review_complete": False, "merge_authorized": False}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("changes_json")
    parser.add_argument("--head-sha", required=True)
    parser.add_argument("--base-sha", required=True)
    args = parser.parse_args()
    try:
        with open(args.changes_json, encoding="utf-8") as stream:
            data = json.load(stream)
        print(json.dumps(build_envelope(data, args.head_sha, args.base_sha), ensure_ascii=False))
    except (OSError, ValueError, UnicodeError):
        print(json.dumps({"status": "BLOCKED", "reason": "invalid_review_request", "merge_authorized": False}))
        raise SystemExit(1)


if __name__ == "__main__":
    main()
