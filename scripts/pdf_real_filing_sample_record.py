"""Record a locally supplied filing PDF and a claimed public source for later review.

A URL and a local PDF hash are evidence identifiers, not proof that the file
came from that URL or that financial numbers are accurate.
"""
import argparse
import json
from pathlib import Path
from urllib.parse import urlsplit

from scripts.disclosure_pdf_fingerprint import fingerprint

MAX_URL_LENGTH = 2048


def make_sample_record(pdf, symbol, announcement_date, source_url):
    if not isinstance(source_url, str) or len(source_url) > MAX_URL_LENGTH:
        raise ValueError("invalid source URL")
    parsed = urlsplit(source_url)
    if (parsed.scheme != "https" or not parsed.hostname or
            parsed.username is not None or parsed.password is not None or
            parsed.fragment or parsed.port not in (None, 443)):
        raise ValueError("source must be a plain HTTPS URL")
    if parsed.hostname.lower() not in (
        "static.cninfo.com.cn", "disc.static.szse.cn", "ir.gf.com.cn"
    ):
        raise ValueError("source hostname not in approved sample list")
    evidence = fingerprint(Path(pdf), symbol, announcement_date)
    return {
        "schema_version": 1,
        "symbol": symbol,
        "announcement_date_claimed": announcement_date,
        "source_url_claimed": source_url,
        "file_sha256": evidence["file_sha256"],
        "source_file_match_verified": False,
        "official_origin_verified": False,
        "financial_meaning_verified": False,
        "manual_checks_required": [
            "Open the public announcement and compare its PDF with the local file",
            "Confirm announcement date and company identifier",
            "Inspect sampled pages and table regions visually",
        ],
    }


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--pdf", required=True)
    parser.add_argument("--symbol", required=True)
    parser.add_argument("--announcement-date", required=True)
    parser.add_argument("--source-url", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args(argv)
    if Path(args.output).resolve() == Path(args.pdf).resolve():
        raise ValueError("output cannot overwrite source PDF")
    record = make_sample_record(
        args.pdf, args.symbol, args.announcement_date, args.source_url)
    target = Path(args.output)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(record, ensure_ascii=False, indent=2) + "\n",
                      encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
