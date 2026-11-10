"""One offline artifact for PDF table evidence, structural checks and review text."""
import argparse
import json
import os
from pathlib import Path
import tempfile

from scripts.financial_filing_evidence_bundle import _pdf_digest
from scripts.financial_table_package_validation import validate_table_review_package
from scripts.financial_table_review_annotations import record_table_reviews, review_package_sha256
from scripts.financial_table_review_package import build_review_package
from scripts.financial_table_review_report import render_review_markdown


def build_financial_review_artifact(pdf_path, symbol, announcement_date, pages,
                                    *, annotations=None, max_rows=100):
    """Extract and validate once; return evidence and presentation, never acceptance."""
    package = build_review_package(pdf_path, symbol, announcement_date, pages)
    validation = validate_table_review_package(package)
    digest = review_package_sha256(package)
    if annotations is None:
        annotations = {"file_sha256": package["file_sha256"], "package_sha256": digest, "decisions": []}
    record = record_table_reviews(package, annotations)
    report = render_review_markdown(package, annotations, max_rows=max_rows)
    if _pdf_digest(pdf_path) != package["file_sha256"]:
        raise ValueError("PDF changed before review artifact completed")
    return {"schema_version": "0.1",
            "status": "REVIEW_MATERIALS_READY_UNVERIFIED" if package["candidate_count"] else "NO_NUMERIC_EVIDENCE",
            "package": package, "validation": validation,
            "review_record": {key: value for key, value in record.items() if key != "package"},
            "report_markdown": report, "release_evidence_accepted": False,
            "official_origin_verified": False, "financial_meaning_verified": False,
            "limitations": ["A structural pass is not financial or source verification.",
                            "Reviewer labels are caller assertions, not authenticated identities.",
                            "Consolidation scope and original evidence blockers remain unresolved."]}


def _unique_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("duplicate annotation JSON key")
        result[key] = value
    return result


def _annotations(path):
    with Path(path).open("rb") as stream:
        raw = stream.read(5 * 1024 * 1024 + 1)
    if len(raw) > 5 * 1024 * 1024:
        raise ValueError("annotation JSON too large")
    try:
        result = json.loads(raw, object_pairs_hook=_unique_object)
    except (ValueError, RecursionError, UnicodeError) as exc:
        raise ValueError("invalid annotation JSON") from exc
    if not isinstance(result, dict):
        raise ValueError("annotation JSON must be an object")
    return result


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--pdf", required=True)
    parser.add_argument("--symbol", required=True)
    parser.add_argument("--announcement-date", required=True)
    parser.add_argument("--pages", required=True)
    parser.add_argument("--annotations")
    parser.add_argument("--max-rows", type=int, default=100)
    parser.add_argument("--output", required=True)
    args = parser.parse_args(argv)
    output = Path(args.output)
    sources = [Path(args.pdf)] + ([Path(args.annotations)] if args.annotations else [])
    if output.is_symlink() or output.resolve() in [source.resolve() for source in sources]:
        raise ValueError("output must not overwrite review inputs")
    try:
        pages = [int(value) for value in args.pages.split(",")]
    except ValueError as exc:
        raise ValueError("invalid pages") from exc
    artifact = build_financial_review_artifact(args.pdf, args.symbol, args.announcement_date, pages,
                                              annotations=_annotations(args.annotations) if args.annotations else None,
                                              max_rows=args.max_rows)
    output.parent.mkdir(parents=True, exist_ok=True)
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", dir=output.parent, delete=False) as stream:
            temporary = Path(stream.name)
            json.dump(artifact, stream, ensure_ascii=False, indent=2, allow_nan=False)
            stream.write("\n")
        os.replace(temporary, output)
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
