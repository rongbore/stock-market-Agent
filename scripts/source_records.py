"""Validate source metadata before it is used as report evidence.

This module does not fetch market data. Sources must be supplied by trusted
adapters; a valid record is not proof that the source content is accurate.
"""
from datetime import datetime
from urllib.parse import urlsplit

ALLOWED_KINDS = {"price", "fundamental", "filing", "news", "macro"}


def _parse_timestamp(value, field):
    if not isinstance(value, str):
        raise ValueError(f"{field} must be an ISO-8601 timestamp string")
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ValueError(f"{field} must be ISO-8601") from exc
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise ValueError(f"{field} must include a timezone")
    return parsed


def validate_source_record(record, *, analysis_cutoff=None, require_retrieved_by_cutoff=False):
    """Validate one record; reject unverified or future-dated evidence."""
    if not isinstance(record, dict):
        raise ValueError("source record must be a mapping")
    if record.get("kind") not in ALLOWED_KINDS:
        raise ValueError("unsupported source kind")
    for field in ("provider", "symbol", "url", "retrieved_at", "published_at"):
        if not isinstance(record.get(field), str) or not record[field].strip():
            raise ValueError(f"missing {field}")
    if any(ord(char) <= 32 or ord(char) == 127 for char in record["url"]):
        raise ValueError("source URL contains whitespace or control characters")
    try:
        parsed_url = urlsplit(record["url"])
        parsed_url.port  # Reject malformed or out-of-range ports.
    except ValueError as exc:
        raise ValueError("invalid source URL") from exc
    if parsed_url.scheme != "https" or not parsed_url.hostname or parsed_url.username or parsed_url.password:
        raise ValueError("source URL must be HTTPS without embedded credentials")
    retrieved = _parse_timestamp(record["retrieved_at"], "retrieved_at")
    published = _parse_timestamp(record["published_at"], "published_at")
    if published > retrieved:
        raise ValueError("published_at cannot be after retrieved_at")
    if analysis_cutoff is not None:
        cutoff = _parse_timestamp(analysis_cutoff, "analysis_cutoff")
        if published > cutoff:
            raise ValueError("source was published after the analysis cutoff")
        if require_retrieved_by_cutoff and retrieved > cutoff:
            raise ValueError("source was retrieved after the analysis cutoff")
    return True
