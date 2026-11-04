"""Offline PDF evidence fingerprinting; no network and no authenticity claims."""
import argparse
import hashlib
import json
from pathlib import Path

MAX_BYTES = 20 * 1024 * 1024


def fingerprint(path, symbol, announcement_date):
    from scripts.akshare_provider import _symbol
    from datetime import date
    _symbol(symbol)
    if not isinstance(announcement_date, str):
        raise ValueError("invalid announcement date")
    try:
        parsed = date.fromisoformat(announcement_date)
    except ValueError as exc:
        raise ValueError("invalid announcement date") from exc
    if parsed.isoformat() != announcement_date:
        raise ValueError("invalid announcement date")
    file = Path(path)
    if not file.is_file() or file.is_symlink():
        raise ValueError("expected regular PDF file")
    size = file.stat().st_size
    if size < 8 or size > MAX_BYTES:
        raise ValueError("PDF size outside allowed range")
    digest = hashlib.sha256()
    with file.open("rb") as stream:
        header = stream.read(5)
        if header != b"%PDF-":
            raise ValueError("file lacks PDF header")
        digest.update(header)
        while chunk := stream.read(65536):
            digest.update(chunk)
    return {
        "schema_version": "0.1",
        "symbol": symbol,
        "announcement_date": announcement_date,
        "file_sha256": digest.hexdigest(),
        "file_size_bytes": size,
        "pdf_header_present": True,
        "source_content_verified": False,
        "official_origin_verified": False,
        "historical_point_in_time_verified": False,
        "note": "File fingerprint only; not proof of official origin, validity or PDF contents.",
    }


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument("--pdf", required=True)
    parser.add_argument("--symbol", required=True)
    parser.add_argument("--announcement-date", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args(argv)
    result = fingerprint(args.pdf, args.symbol, args.announcement_date)
    target = Path(args.output)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
