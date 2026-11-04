"""Offline PDF character geometry extraction; coordinates are not table semantics."""
import argparse
import json
from pathlib import Path

from scripts.disclosure_pdf_fingerprint import fingerprint
from scripts.financial_pdf_geometry import inspect_spans

MAX_CHARS_PER_PAGE = 2000


def extract_geometry(path, symbol, announcement_date, page_numbers, opener=None):
    """Read bounded character boxes from a local PDF using optional pdfplumber."""
    if not isinstance(page_numbers, list) or not 1 <= len(page_numbers) <= 100:
        raise ValueError("page numbers must be a nonempty list of at most 100")
    if any(type(n) is not int or not 1 <= n <= 10000 for n in page_numbers):
        raise ValueError("invalid PDF page number")
    if len(set(page_numbers)) != len(page_numbers):
        raise ValueError("duplicate PDF page number")
    file = Path(path)
    before = fingerprint(file, symbol, announcement_date)
    if opener is None:
        try:
            import pdfplumber
        except ImportError as exc:
            raise RuntimeError("Install pdfplumber for local PDF geometry extraction") from exc
        opener = pdfplumber.open
    try:
        with opener(file) as pdf:
            if any(n > len(pdf.pages) for n in page_numbers):
                raise ValueError("PDF page number out of range")
            spans = []
            for number in page_numbers:
                chars = pdf.pages[number - 1].chars
                if not isinstance(chars, list) or len(chars) > MAX_CHARS_PER_PAGE:
                    raise ValueError("too many PDF characters on requested page")
                for char in chars:
                    spans.append({
                        "page": number,
                        "text": char["text"],
                        "bbox": [char["x0"], char["top"], char["x1"], char["bottom"]],
                    })
                if len(spans) > 2000:
                    raise ValueError("too many geometry spans")
            inspect_spans(spans)
    except (ValueError, RuntimeError):
        raise
    except Exception as exc:
        raise ValueError("unable to extract PDF geometry") from exc
    after = fingerprint(file, symbol, announcement_date)
    if before["file_sha256"] != after["file_sha256"]:
        raise ValueError("PDF changed during geometry extraction")
    return {
        "file_sha256": before["file_sha256"],
        "spans": spans,
        "geometry_extracted_unverified": True,
        "official_origin_verified": False,
        "financial_meaning_verified": False,
        "column_ownership_verified": False,
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
        numbers = [int(n) for n in args.pages.split(",")]
    except ValueError as exc:
        raise ValueError("invalid page number list") from exc
    result = extract_geometry(args.pdf, args.symbol, args.announcement_date, numbers)
    target = Path(args.output)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
