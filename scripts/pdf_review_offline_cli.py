"""Offline CLI to validate PDF rectangle review annotations against a saved manifest."""
import argparse
import json
from pathlib import Path

from scripts.pdf_manual_review_validation import validate_review_annotations

MAX_JSON_BYTES = 1024 * 1024


def read_json_object(path):
    file = Path(path)
    if not file.is_file() or file.stat().st_size > MAX_JSON_BYTES:
        raise ValueError("missing or oversized JSON file")
    with file.open("r", encoding="utf-8") as handle:
        value = json.load(handle)
    if not isinstance(value, dict):
        raise ValueError("JSON root must be an object")
    return value


def validate_review_files(manifest_path, annotations_path):
    """Return a report with conservative verification flags."""
    manifest = read_json_object(manifest_path)
    annotations = read_json_object(annotations_path)
    return validate_review_annotations(manifest, annotations)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", required=True)
    parser.add_argument("--annotations", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args(argv)
    target = Path(args.output)
    if target.resolve() in (
        Path(args.manifest).resolve(), Path(args.annotations).resolve()
    ):
        raise ValueError("output cannot overwrite input files")
    report = validate_review_files(args.manifest, args.annotations)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n",
                      encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
