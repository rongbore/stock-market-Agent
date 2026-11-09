"""Build offline table review evidence; never produce verified financial claims."""
import argparse
import json
import os
from pathlib import Path
import tempfile

from scripts.financial_filing_evidence_bundle import _pdf_digest
from scripts.financial_table_metric_hints import table_metric_hints
from scripts.offline_pdf_table_cells import extract_table_cells


def build_review_package(pdf_path, symbol, announcement_date, pages):
    digest = _pdf_digest(pdf_path)
    extracted = extract_table_cells(pdf_path, symbol, announcement_date, pages)
    if extracted["file_sha256"] != digest or _pdf_digest(pdf_path) != digest:
        raise ValueError("PDF changed during review extraction")
    result = table_metric_hints(extracted["cells"])
    for candidate in result["candidates"]:
        missing = [field for field in ("metric", "unit", "period")
                   if candidate[field + "_hint_unverified"] is None]
        candidate["review_blockers"] = missing + ["consolidation_scope", "manual_verification"]
        candidate["consolidation_scope"] = None
    return {"schema_version": "0.1", "symbol": symbol,
            "announcement_date_supplied_unverified": announcement_date,
            "file_sha256": digest, "pages": pages,
            "status": "PENDING_MANUAL_VERIFICATION",
            "candidates": result["candidates"],
            "official_origin_verified": False, "source_content_verified": False,
            "financial_meaning_verified": False, "column_ownership_verified": False,
            "historical_point_in_time_verified": False}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--pdf", required=True)
    parser.add_argument("--symbol", required=True)
    parser.add_argument("--announcement-date", required=True)
    parser.add_argument("--pages", required=True, help="Comma-separated 1-based page numbers")
    parser.add_argument("--output", required=True)
    args = parser.parse_args(argv)
    if Path(args.pdf).resolve() == Path(args.output).resolve():
        raise ValueError("output must not overwrite source PDF")
    try:
        pages = [int(value) for value in args.pages.split(",")]
    except ValueError as exc:
        raise ValueError("invalid pages") from exc
    result = build_review_package(args.pdf, args.symbol, args.announcement_date, pages)
    target = Path(args.output)
    target.parent.mkdir(parents=True, exist_ok=True)
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", dir=target.parent,
                                         delete=False) as stream:
            temporary = Path(stream.name)
            json.dump(result, stream, ensure_ascii=False, indent=2)
            stream.write("\n")
        os.replace(temporary, target)
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
