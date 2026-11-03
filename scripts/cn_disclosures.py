"""Normalize Chinese listed-company disclosure metadata without fetching data.

Provider adapters must supply authentic URLs and announcement dates. A date
without an official publication time is not sufficient for same-day historical
point-in-time validation.
"""
from datetime import date, datetime, timedelta, timezone
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
    timestamp = None
    if published_at is not None:
        if not isinstance(published_at, str):
            raise ValueError("published_at must be a timezone-aware ISO timestamp")
        try:
            timestamp = datetime.fromisoformat(published_at.replace("Z", "+00:00"))
        except ValueError as exc:
            raise ValueError("invalid published_at") from exc
        if timestamp.tzinfo is None or timestamp.utcoffset() is None:
            raise ValueError("published_at requires timezone")
        shanghai_date = timestamp.astimezone(timezone(timedelta(hours=8))).date()
        if shanghai_date != published_date:
            raise ValueError("published_at Shanghai date and announcement_date disagree")
        if analysis_date is not None:
            day_end = datetime.combine(cutoff + timedelta(days=1), datetime.min.time(),
                                       tzinfo=timezone(timedelta(hours=8)))
            if timestamp >= day_end:
                raise ValueError("published_at is after the analysis date in Shanghai")
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


def historical_disclosure_eligibility(record, *, analysis_date):
    """Conservative date-only gate; never infer an official publication hour.

    This is an eligibility *screen*, not proof that content was historically
    available or authentic. Same-day disclosures require independent timing
    verification before use as historical evidence.
    """
    normalized = normalize_disclosure(record, analysis_date=analysis_date)
    announcement = date.fromisoformat(normalized["announcement_date"])
    analysis = date.fromisoformat(analysis_date)
    if announcement < analysis:
        return {
            "eligible_by_announcement_date": True,
            "status": "prior_date_candidate",
            "historical_point_in_time_verified": False,
            "reason": "Announcement date precedes analysis date; source availability remains unverified.",
        }
    return {
        "eligible_by_announcement_date": False,
        "status": "same_day_requires_verification",
        "historical_point_in_time_verified": False,
        "reason": "Same-day publication time and historical availability require independent verification.",
    }
