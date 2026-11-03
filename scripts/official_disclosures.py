"""Offline official-domain disclosure metadata adapter.

This module does not fetch a URL or authenticate its contents. Host allowlisting
only limits candidate metadata to recognized exchange/disclosure domains.
"""
from urllib.parse import urlsplit

from .cn_disclosures import normalize_disclosure

OFFICIAL_HOSTS = {
    "cninfo": frozenset({"www.cninfo.com.cn", "static.cninfo.com.cn"}),
    "sse": frozenset({"www.sse.com.cn"}),
    "szse": frozenset({"www.szse.cn"}),
}


def adapt_official_disclosure(record, *, source, analysis_date):
    """Validate an offline notice and return normalized, unverified metadata."""
    if source not in OFFICIAL_HOSTS:
        raise ValueError("unsupported official disclosure source")
    if not isinstance(record, dict):
        raise ValueError("disclosure must be a mapping")
    url = record.get("url")
    if not isinstance(url, str):
        raise ValueError("disclosure URL required")
    parsed = urlsplit(url)
    if (parsed.scheme != "https" or parsed.hostname not in OFFICIAL_HOSTS[source]
            or parsed.username or parsed.password or parsed.port not in (None, 443)):
        raise ValueError("disclosure URL must use the selected official HTTPS host")
    normalized = normalize_disclosure(
        {**record, "provider": source.upper()}, analysis_date=analysis_date
    )
    if source == "sse" and not normalized["symbol"].endswith(".SS"):
        raise ValueError("SSE notice requires .SS symbol")
    if source == "szse" and not normalized["symbol"].endswith(".SZ"):
        raise ValueError("SZSE notice requires .SZ symbol")
    normalized["source_domain_allowlisted"] = True
    normalized["source_content_verified"] = False
    return normalized
