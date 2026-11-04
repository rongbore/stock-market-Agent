"""Extract unverified drawn-rectangle region candidates from a local PDF."""
import argparse
import json
from pathlib import Path

from scripts.disclosure_pdf_fingerprint import fingerprint
from scripts.financial_pdf_rectangle_candidates import rectangle_region_candidates

MAX_RECTS_PER_PAGE = 2000


def extract_rectangle_candidates(path, symbol, announcement_date, page_numbers, opener=None):
    """Read bounded PDF drawing rectangles, fingerprinting the file before and after."""
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
            raise RuntimeError("Install pdfplumber for local PDF rectangle extraction") from exc
        opener = pdfplumber.open
    try:
        with opener(file) as pdf:
            if any(n > len(pdf.pages) for n in page_numbers):
                raise ValueError("PDF page number out of range")
            rectangles = []
            for number in page_numbers:
                rects = pdf.pages[number - 1].rects
                if not isinstance(rects, list) or len(rects) > MAX_RECTS_PER_PAGE:
                    raise ValueError("too many PDF rectangles on requested page")
                for rect in rects:
                    rectangles.append({
                        "page": number, "x0": rect["x0"], "top": rect["top"],
                        "x1": rect["x1"], "bottom": rect["bottom"],
                    })
                if len(rectangles) > 2000:
                    raise ValueError("too many PDF rectangles")
            result = rectangle_region_candidates(rectangles)
    except (ValueError, RuntimeError):
        raise
    except Exception as exc:
        raise ValueError("unable to extract PDF rectangles") from exc
    after = fingerprint(file, symbol, announcement_date)
    if before["file_sha256"] != after["file_sha256"]:
        raise ValueError("PDF changed during rectangle extraction")
    return {
        "file_sha256": before["file_sha256"],
        **result,
        "official_origin_verified": False,
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
        pages = [int(p) for p in args.pages.split(",")]
    except ValueError as exc:
        raise ValueError("invalid page number list") from exc
    result = extract_rectangle_candidates(
        args.pdf, args.symbol, args.announcement_date, pages)
    target = Path(args.output)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
