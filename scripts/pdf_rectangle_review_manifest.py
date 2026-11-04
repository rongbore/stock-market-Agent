"""Generate an offline, unverified review manifest for PDF rectangle candidates."""
import argparse
import json
from pathlib import Path

from scripts.offline_pdf_rectangle_extract import extract_rectangle_candidates


def build_review_manifest(path, symbol, announcement_date, pages, opener=None):
    """Extract candidate rectangles and attach explicit manual-review status."""
    result = extract_rectangle_candidates(
        path, symbol, announcement_date, pages, opener=opener)
    return {
        "schema_version": 1,
        "symbol": symbol,
        "announcement_date_claimed": announcement_date,
        "file_sha256": result["file_sha256"],
        "pages_requested": pages,
        "candidate_count": len(result["regions"]),
        "ambiguous_overlap_count": result["ambiguous_overlap_count"],
        "candidates": [
            {
                "page": region["page"],
                "bbox": region["bbox"],
                "review_status": "pending_manual_review",
                "is_financial_table_verified": False,
            }
            for region in result["regions"]
        ],
        "official_origin_verified": False,
        "table_boundaries_verified": False,
        "financial_meaning_verified": False,
        "warning": (
            "Rectangles are only geometry candidates; verify source, table identity, "
            "period, row and column against the original PDF manually."
        ),
    }


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument("--pdf", required=True)
    parser.add_argument("--symbol", required=True)
    parser.add_argument("--announcement-date", required=True)
    parser.add_argument("--pages", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args(argv)
    try:
        pages = [int(part) for part in args.pages.split(",")]
    except ValueError as exc:
        raise ValueError("invalid page number list") from exc
    report = build_review_manifest(args.pdf, args.symbol, args.announcement_date, pages)
    destination = Path(args.output)
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n",
                           encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
