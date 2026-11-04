"""Offline, immutable report archive with content-based deduplication."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import tempfile

SAFE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.-]{0,79}$")


def archive_report(source, archive_root, ticker, analysis_date):
    if not SAFE.fullmatch(ticker) or not re.fullmatch(r"\d{4}-\d{2}-\d{2}", analysis_date):
        raise ValueError("invalid archive identifier")
    source = Path(source).resolve(strict=True)
    root = Path(archive_root).resolve()
    if not source.is_dir() or source.is_symlink():
        raise ValueError("source must be a directory")
    if root == source or root in source.parents or source in root.parents:
        raise ValueError("archive root and source must not overlap")
    files = []
    for path in sorted(source.rglob("*")):
        if path.is_symlink():
            raise ValueError("symlinks are forbidden")
        if path.is_file():
            relative = path.relative_to(source).as_posix()
            if len(files) >= 1000:
                raise ValueError("too many files")
            if path.stat().st_size > 50_000_000:
                raise ValueError("oversized file")
            digest = hashlib.sha256(path.read_bytes()).hexdigest()
            files.append({"path": relative, "sha256": digest})
    if not files:
        raise ValueError("empty report")
    manifest_bytes = json.dumps(files, sort_keys=True, separators=(",", ":")).encode()
    digest = hashlib.sha256(manifest_bytes).hexdigest()
    destination = root / ticker / analysis_date / digest
    if destination.exists():
        manifest = destination / "_archive_manifest.json"
        if not manifest.is_file() or json.loads(manifest.read_text(encoding="utf-8")).get("files") != files:
            raise ValueError("existing archive is incomplete or inconsistent")
        for item in files:
            path = destination / item["path"]
            if not path.is_file() or path.is_symlink() or hashlib.sha256(path.read_bytes()).hexdigest() != item["sha256"]:
                raise ValueError("existing archive contents have changed")
        return destination, False
    destination.parent.mkdir(parents=True, exist_ok=True)
    temporary = Path(tempfile.mkdtemp(prefix=".archive-", dir=destination.parent))
    try:
        for item in files:
            origin = source / item["path"]
            target = temporary / item["path"]
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(origin, target)
            if hashlib.sha256(target.read_bytes()).hexdigest() != item["sha256"]:
                raise ValueError("source changed while archiving")
        (temporary / "_archive_manifest.json").write_text(
            json.dumps({"schema_version": 1, "content_sha256": digest, "files": files},
                       ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        if destination.exists():
            raise ValueError("concurrent archive creation detected")
        os.rename(temporary, destination)
    finally:
        if temporary.exists():
            shutil.rmtree(temporary)
    return destination, True


def main():
    parser = argparse.ArgumentParser(description="Archive existing offline report files")
    parser.add_argument("--source", required=True)
    parser.add_argument("--archive-root", required=True)
    parser.add_argument("--ticker", required=True)
    parser.add_argument("--analysis-date", required=True)
    args = parser.parse_args()
    path, created = archive_report(args.source, args.archive_root, args.ticker, args.analysis_date)
    print(json.dumps({"archive": str(path), "created": created}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
