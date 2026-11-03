"""Normalize Chinese listed-company disclosure metadata without fetching data.

Provider adapters must supply authentic URLs and announcement dates. A date
without an official publication time is not sufficient for same-day historical
point-in-time validation.
"""
from datetime import date, datetime
from urllib.parse import urlsplit


def normalize_disclosure(record, *, analysis_date=None):
    """Return metadata, including an explicit uncertainty flag for date-only data."""
    if not isinstance(record, dict):
        raise ValueError("disclosure must be a mapping")
    for field in ("symbol", "title", "provider", "url", "announcement_date"):
        if not isinstance(record.get(field), str) or not record[field].strip():
            raise ValueError(f"missing {field}")
    symbol = record["symbol"].strip().upper()
    if not (symbol.endswith(".SZ") or symbol.endswith(".SS")):
        raise ValueError("A-share symbol must end with .SZ or .SS")
    prefix = symbol.rsplit(".", 1)[0]
    if len(prefix) != 6 or not prefix.isdigit():
        raise ValueError("A-share symbol requires six digits")
    url = urlsplit(record["url"])
    if url.scheme != "https" or not url.hostname or url.username or url.password:
        raise ValueError("disclosure URL must be HTTPS without credentials")
    try:
        published_date = date.fromisoformat(record["announcement_date"])
    except ValueError as exc:
        raise ValueError("announcement_date must be YYYY-MM-DD") from exc
    if analysis_date is not None:
        try:
            cutoff = date.fromisoformat(analysis_date)
        except ValueError as exc:
            raise ValueError("analysis_date must be YYYY-MM-DD") from exc
        if published_date > cutoff:
            raise ValueError("disclosure date is after analysis date")
    published_at = record.get("published_at")
    if published_at is not None:
        if not isinstance(published_at, str):
            raise ValueError("published_at must be a timezone-aware ISO timestamp")
        try:
            timestamp = datetime.fromisoformat(published_at.replace("Z", "+00:00"))
        except ValueError as exc:
            raise ValueError("invalid published_at") from exc
        if timestamp.tzinfo is None or timestamp.utcoffset() is None:
            raise ValueError("published_at requires timezone")
        if timestamp.date() != published_date:
            raise ValueError("published_at date and announcement_date disagree")
    return {
        "symbol": symbol,
        "title": record["title"].strip(),
        "provider": record["provider"].strip(),
        "url": record["url"],
        "announcement_date": published_date.isoformat(),
        "published_at": published_at,
        "publication_time_verified": False,
        "same_day_historical_eligibility": "unknown",
    }
