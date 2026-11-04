"""Bounded local PDF page text extraction, with explicit unverified provenance."""
import argparse
import json
from pathlib import Path

from scripts.disclosure_pdf_fingerprint import fingerprint


def extract_pages(path, symbol, announcement_date, page_numbers, reader_factory=None):
    """Extract 1-based PDF pages; verify local bytes, not official origin or semantics."""
    if not isinstance(page_numbers, list) or not 1 <= len(page_numbers) <= 100:
        raise ValueError("page numbers must be a nonempty list of at most 100")
    if any(type(n) is not int or n < 1 or n > 10000 for n in page_numbers):
        raise ValueError("invalid PDF page number")
    if len(set(page_numbers)) != len(page_numbers):
        raise ValueError("duplicate PDF page number")
    file = Path(path)
    before = fingerprint(file, symbol, announcement_date)
    if reader_factory is None:
        try:
            from pypdf import PdfReader
        except ImportError as exc:
            raise RuntimeError("Install pypdf to extract local PDF page text") from exc
        reader_factory = PdfReader
    try:
        with file.open("rb") as stream:
            reader = reader_factory(stream)
            if reader.is_encrypted:
                raise ValueError("encrypted PDF not supported")
            total = len(reader.pages)
            if any(n > total for n in page_numbers):
                raise ValueError("PDF page number out of range")
            records = []
            for n in page_numbers:
                value = reader.pages[n - 1].extract_text()
                if not isinstance(value, str):
                    value = ""
                if len(value) > 100000:
                    raise ValueError("extracted page text too large")
                records.append({
                    "file_sha256": before["file_sha256"], "page": n,
                    "text": value, "text_extraction_status": "text_extracted_unverified" if value.strip() else "no_extractable_text",
                    "official_origin_verified": False, "financial_meaning_verified": False,
                })
    except (ValueError, RuntimeError):
        raise
    except Exception as exc:
        raise ValueError("unable to parse local PDF") from exc
    after = fingerprint(file, symbol, announcement_date)
    if before["file_sha256"] != after["file_sha256"]:
        raise ValueError("PDF changed during extraction")
    return records


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument("--pdf", required=True)
    parser.add_argument("--symbol", required=True)
    parser.add_argument("--announcement-date", required=True)
    parser.add_argument("--pages", required=True, help="Comma-separated 1-based page numbers")
    parser.add_argument("--output", required=True)
    args = parser.parse_args(argv)
    try:
        numbers = [int(n) for n in args.pages.split(",")]
    except ValueError as exc:
        raise ValueError("invalid page number list") from exc
    records = extract_pages(args.pdf, args.symbol, args.announcement_date, numbers)
    target = Path(args.output)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(records, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
