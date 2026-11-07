"""Produce complete PR changed-file metadata from a local git checkout.

Run only in a read-only, trusted job after fetching both exact SHAs.
Do not run this module from a privileged pull_request_target checkout.
"""
import argparse
import json
import re
import subprocess

SHA = re.compile(r"^[0-9a-f]{40}$")
MAX_DIFF_BYTES = 2_000_000
MAX_FILES = 50


def git(*args):
    return subprocess.run(
        ["git", *args], stdout=subprocess.PIPE, stderr=subprocess.PIPE,
        check=True, timeout=20
    ).stdout


def collect(base_sha, head_sha):
    if not SHA.fullmatch(base_sha) or not SHA.fullmatch(head_sha):
        raise ValueError("invalid_sha")
    # Verify object identity and existence before diffing.
    for sha in (base_sha, head_sha):
        if git("rev-parse", "--verify", sha + "^{commit}").decode().strip() != sha:
            raise ValueError("missing_commit")
    base = git("merge-base", base_sha, head_sha).decode().strip()
    if base != base_sha:
        raise ValueError("base_not_ancestor")
    raw = git("diff", "--raw", "-z", "--abbrev=40", "--no-renames", base_sha, head_sha)
    parts = raw.split(b"\0")
    if parts[-1:] == [b""]:
        parts.pop()
    if len(parts) % 2:
        raise ValueError("incomplete_raw_diff")
    if not 1 <= len(parts) // 2 <= MAX_FILES:
        raise ValueError("invalid_file_count")
    result = []
    for i in range(0, len(parts), 2):
        header = parts[i].decode("ascii", "strict")
        path = parts[i + 1].decode("utf-8", "strict")
        match = re.fullmatch(r":([0-7]{6}) ([0-7]{6}) ([0-9a-f]{40}) ([0-9a-f]{40}) ([AMDT])", header)
        if not match:
            raise ValueError("unsupported_change")
        old_mode, mode, _, _, kind = match.groups()
        if kind not in ("A", "M") or mode != "100644" or (kind == "M" and old_mode != "100644"):
            raise ValueError("unsafe_file_change")
        if "\n" in path or "\r" in path or not path.startswith("docs/") or not path.endswith(".md"):
            raise ValueError("not_documentation")
        # Use exact full-file added content as conservative scanner input.
        blob = git("show", head_sha + ":" + path)
        if len(blob) > MAX_DIFF_BYTES or b"\0" in blob:
            raise ValueError("binary_or_oversized")
        text = blob.decode("utf-8", "strict")
        # Prefix each line as added: classify the entire file, not a truncated API patch.
        patch = "@@ full-file content @@\n" + "".join("+" + line + "\n" for line in text.splitlines())
        result.append({"filename": path, "status": "added" if kind == "A" else "modified",
                       "type": "file", "mode": mode, "binary": False, "patch": patch})
    return result


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-sha", required=True)
    parser.add_argument("--head-sha", required=True)
    args = parser.parse_args()
    try:
        print(json.dumps(collect(args.base_sha, args.head_sha), ensure_ascii=False))
    except (ValueError, UnicodeError, subprocess.SubprocessError, OSError):
        print(json.dumps({"status": "BLOCKED", "reasons": ["untrusted_or_incomplete_diff"]}))
        raise SystemExit(1)


if __name__ == "__main__":
    main()
