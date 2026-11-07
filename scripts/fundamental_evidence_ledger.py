"""Offline fundamental evidence ledger; no scraping, prediction or trading.

Input is a manually supplied list of source records, not automatically verified facts.
"""
import argparse
import json
from datetime import date
from pathlib import Path
from urllib.parse import urlsplit


ALLOWED_KINDS = {"annual_report", "quarterly_report", "interim_report", "company_announcement"}


def _iso_date(value):
    if not isinstance(value, str):
        raise ValueError("invalid publication date")
    try:
        parsed = date.fromisoformat(value)
    except ValueError as exc:
        raise ValueError("invalid publication date") from exc
    if parsed.isoformat() != value:
        raise ValueError("publication date must use YYYY-MM-DD")
    return value


def _source_url(value):
    if not isinstance(value, str) or len(value) > 2048 or any(ord(c) < 32 for c in value):
        raise ValueError("invalid source URL")
    parsed = urlsplit(value)
    if parsed.scheme != "https" or not parsed.hostname or parsed.username or parsed.password:
        raise ValueError("source URL must be public HTTPS")
    if parsed.hostname in ("localhost",) or parsed.hostname.endswith(".local"):
        raise ValueError("local source URL forbidden")
    return value


def build_ledger(records, symbol):
    if not isinstance(symbol, str) or not symbol.strip() or len(symbol) > 40:
        raise ValueError("invalid symbol")
    if not isinstance(records, list) or len(records) > 500:
        raise ValueError("invalid evidence collection")
    items, seen = [], set()
    for row in records:
        if not isinstance(row, dict):
            raise ValueError("invalid evidence record")
        kind, title = row.get("kind"), row.get("title")
        if kind not in ALLOWED_KINDS:
            raise ValueError("unsupported evidence kind")
        if not isinstance(title, str) or not title.strip() or len(title) > 300:
            raise ValueError("invalid evidence title")
        published = _iso_date(row.get("published_date"))
        url = _source_url(row.get("source_url"))
        if row.get("symbol") != symbol:
            raise ValueError("evidence symbol mismatch")
        key = (kind, published, url)
        if key in seen:
            raise ValueError("duplicate evidence record")
        seen.add(key)
        items.append({
            "kind": kind, "title": title, "published_date": published,
            "source_url": url, "symbol": symbol,
            "source_content_verified": False,
            "historical_point_in_time_verified": False,
        })
    items.sort(key=lambda x: (x["published_date"], x["kind"], x["source_url"]), reverse=True)
    return {"schema_version": "0.1", "symbol": symbol,
            "evidence_count": len(items), "records": items,
            "content_verified": False,
            "interpretation": "仅为人工录入的资料索引；未验证链接内容、披露主体或历史时点。"}


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", required=True)
    parser.add_argument("--symbol", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args(argv)
    raw = json.loads(Path(args.input).read_text(encoding="utf-8"))
    result = build_ledger(raw, args.symbol)
    Path(args.output).write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
