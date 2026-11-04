"""Validate manually transcribed financial claims against local PDF fingerprints.

No PDF parsing, financial inference, or official authenticity claims.
"""
from datetime import date
from decimal import Decimal, InvalidOperation
import re

METRICS = {"revenue", "net_profit_attributable", "total_assets", "operating_cash_flow"}
UNITS = {"CNY", "CNY_10000", "CNY_100000000"}


def validate_claims(claims, fingerprints, symbol, research_date):
    if not isinstance(claims, list) or len(claims) > 100:
        raise ValueError("claims must be a list of at most 100")
    if not isinstance(fingerprints, list) or len(fingerprints) > 100:
        raise ValueError("fingerprints must be a list of at most 100")
    if not isinstance(research_date, str):
        raise ValueError("invalid research date")
    try:
        cutoff = date.fromisoformat(research_date)
    except ValueError as exc:
        raise ValueError("invalid research date") from exc
    if cutoff.isoformat() != research_date:
        raise ValueError("invalid research date")
    available = set()
    for fp in fingerprints:
        if not isinstance(fp, dict) or fp.get("symbol") != symbol:
            raise ValueError("fingerprint symbol mismatch")
        digest = fp.get("file_sha256")
        if not isinstance(digest, str) or not re.fullmatch(r"[0-9a-f]{64}", digest):
            raise ValueError("invalid fingerprint SHA-256")
        if fp.get("official_origin_verified") is not False or fp.get("source_content_verified") is not False:
            raise ValueError("unsupported fingerprint verification claim")
        available.add(digest)
    result = []
    for claim in claims:
        if not isinstance(claim, dict) or claim.get("symbol") != symbol:
            raise ValueError("claim symbol mismatch")
        metric, unit, value = claim.get("metric"), claim.get("unit"), claim.get("value")
        if metric not in METRICS or unit not in UNITS:
            raise ValueError("unsupported financial metric or unit")
        if not isinstance(value, str) or not re.fullmatch(r"-?[0-9]+(?:\\.[0-9]+)?", value):
            raise ValueError("financial value must be a decimal string")
        try:
            number = Decimal(value)
        except InvalidOperation as exc:
            raise ValueError("invalid financial value") from exc
        if not number.is_finite() or len(value) > 60:
            raise ValueError("invalid financial value")
        digest = claim.get("file_sha256")
        if digest not in available:
            raise ValueError("claim lacks matching local PDF fingerprint")
        dates = []
        for field in ("period_end", "announcement_date"):
            raw = claim.get(field)
            if not isinstance(raw, str):
                raise ValueError("invalid claim date")
            try:
                parsed = date.fromisoformat(raw)
            except ValueError as exc:
                raise ValueError("invalid claim date") from exc
            if parsed.isoformat() != raw:
                raise ValueError("invalid claim date")
            dates.append(parsed)
        period, announcement = dates
        if period > announcement or announcement > cutoff:
            raise ValueError("claim dates inconsistent with research cutoff")
        page = claim.get("page")
        if isinstance(page, bool) or not isinstance(page, int) or not 1 <= page <= 10000:
            raise ValueError("PDF page number required")
        result.append({
            "symbol": symbol, "metric": metric, "value": value, "unit": unit,
            "period_end": period.isoformat(), "announcement_date": announcement.isoformat(),
            "file_sha256": digest, "page": page,
            "source_content_verified": False, "official_origin_verified": False,
            "historical_point_in_time_verified": False,
            "status": "manually_transcribed_unverified",
        })
    return result
