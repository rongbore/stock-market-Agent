"""Offline CLI for the read-only trusted review artifact pipeline."""
import argparse
import json
from pathlib import Path
import sys

from scripts.trusted_review_artifact_pipeline import verify_trusted_review_artifact

_MAX_METADATA_BYTES = 64 * 1024
_MAX_ARCHIVE_BYTES = 1024 * 1024
_METADATA_KEYS = frozenset({
    "repo", "current_head_sha", "current_base_sha", "expected_request_digest",
    "expected_workflow_id", "expected_workflow_path", "expected_event",
    "trusted_artifact_sha", "trusted_workflow_ref", "trusted_workflow_sha",
    "run", "artifact",
})


def _unique_object(pairs):
    value = {}
    for key, item in pairs:
        if key in value:
            raise ValueError("duplicate metadata key")
        value[key] = item
    return value


def _read_limited(path, maximum):
    with Path(path).open("rb") as source:
        raw = source.read(maximum + 1)
    if len(raw) > maximum:
        raise ValueError("input file too large")
    return raw


def evaluate_files(metadata_path, archive_path):
    """Read bounded offline inputs and return a non-authorizing report."""
    raw = _read_limited(metadata_path, _MAX_METADATA_BYTES)
    try:
        metadata = json.loads(raw.decode("utf-8"), object_pairs_hook=_unique_object)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ValueError("invalid metadata JSON") from exc
    if not isinstance(metadata, dict) or set(metadata) != _METADATA_KEYS:
        raise ValueError("invalid metadata schema")
    archive = _read_limited(archive_path, _MAX_ARCHIVE_BYTES)
    result = verify_trusted_review_artifact(archive_bytes=archive, **metadata)
    return {"status": result["status"], "reason": result["reason"],
            "evidence_authenticated": result["evidence_authenticated"],
            "merge_authorized": False}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--metadata", required=True, help="trusted GitHub metadata JSON")
    parser.add_argument("--archive", required=True, help="downloaded review artifact ZIP")
    args = parser.parse_args(argv)
    try:
        report = evaluate_files(args.metadata, args.archive)
    except (OSError, TypeError, ValueError):
        report = {"status": "manual", "reason": "unable to validate review artifact inputs",
                  "evidence_authenticated": False, "merge_authorized": False}
    print(json.dumps(report, sort_keys=True))
    return 0


if __name__ == "__main__":
    sys.exit(main())
