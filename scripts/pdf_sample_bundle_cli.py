"""Build an offline filing sample bundle from a local PDF and claimed source URL."""
import argparse
import json
from pathlib import Path

from scripts.pdf_real_filing_sample_record import make_sample_record
from scripts.pdf_rectangle_review_manifest import build_review_manifest


def build_sample_bundle(pdf, symbol, announcement_date, source_url, pages, opener=None):
    """Build both evidence records and reject inconsistent PDF fingerprints."""
    source = make_sample_record(pdf, symbol, announcement_date, source_url)
    manifest = build_review_manifest(pdf, symbol, announcement_date, pages, opener=opener)
    if source["file_sha256"] != manifest["file_sha256"]:
        raise ValueError("PDF changed between provenance and geometry extraction")
    return {
        "schema_version": 1,
        "source_record": source,
        "review_manifest": manifest,
        "sample_checked_with_real_pdf_parser": opener is None,
        "official_origin_verified": False,
        "financial_meaning_verified": False,
    }


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--pdf", required=True)
    parser.add_argument("--symbol", required=True)
    parser.add_argument("--announcement-date", required=True)
    parser.add_argument("--source-url", required=True)
    parser.add_argument("--pages", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args(argv)
    try:
        pages = [int(p) for p in args.pages.split(",")]
    except ValueError as exc:
        raise ValueError("invalid page list") from exc
    output = Path(args.output)
    if output.resolve() == Path(args.pdf).resolve():
        raise ValueError("output cannot overwrite PDF")
    bundle = build_sample_bundle(
        args.pdf, args.symbol, args.announcement_date, args.source_url, pages)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(bundle, ensure_ascii=False, indent=2) + "\n",
                      encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
