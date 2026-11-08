"""Join a local filing PDF to time-bounded, manually transcribed claims.

This is a provenance contract only. It does not authenticate the publisher,
read PDF tables, verify claimed numbers, or provide investment advice.
"""
from datetime import date, datetime
from decimal import Decimal, InvalidOperation
import hashlib
import os
import re
import stat
from pathlib import Path
from urllib.parse import urlsplit


METRIC_LABELS = {
    "revenue": "营业总收入",
    "net_profit_attributable": "归属于上市公司股东的净利润",
    "operating_cash_flow": "经营活动产生的现金流量净额",
    "total_assets": "总资产",
}
UNITS = {"CNY", "CNY_10000", "CNY_100000000"}
PERIOD_BASES = {"current_quarter", "year_to_date", "period_end"}
SCOPES = {"consolidated", "parent_company"}
_SHA256 = re.compile(r"^[0-9a-f]{64}$")
_DECIMAL = re.compile(r"^-?[0-9]+(?:\.[0-9]+)?$")
MAX_PDF_BYTES = 20 * 1024 * 1024


def _pdf_digest(path):
    """Hash a bounded regular file without following a symlink at open time."""
    flags = os.O_RDONLY | getattr(os, "O_BINARY", 0) | getattr(os, "O_NOFOLLOW", 0)
    try:
        fd = os.open(path, flags)
    except OSError as exc:
        raise ValueError("unable to open regular PDF without following symlinks") from exc
    try:
        info = os.fstat(fd)
        if not stat.S_ISREG(info.st_mode) or not 8 <= info.st_size <= MAX_PDF_BYTES:
            raise ValueError("PDF size or file type outside allowed range")
        if not hasattr(os, "O_NOFOLLOW"):
            before = os.stat(path, follow_symlinks=False)
            if (not stat.S_ISREG(before.st_mode)
                    or (before.st_dev, before.st_ino) != (info.st_dev, info.st_ino)):
                raise ValueError("PDF path changed or is a symlink")
        with os.fdopen(fd, "rb", closefd=False) as stream:
            header = stream.read(5)
            if header != b"%PDF-":
                raise ValueError("local filing lacks PDF header")
            hasher = hashlib.sha256()
            hasher.update(header)
            tail = header
            while chunk := stream.read(65536):
                hasher.update(chunk)
                tail = (tail + chunk)[-2048:]
            if b"%%EOF" not in tail:
                raise ValueError("local filing lacks a PDF EOF marker")
        return hasher.hexdigest()
    finally:
        os.close(fd)


def _timestamp(value, field):
    if not isinstance(value, str):
        raise ValueError(f"{field} must be an ISO-8601 timestamp")
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ValueError(f"{field} must be an ISO-8601 timestamp") from exc
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise ValueError(f"{field} must include timezone")
    return parsed


def _day(value, field):
    if not isinstance(value, str):
        raise ValueError(f"{field} must be YYYY-MM-DD")
    try:
        parsed = date.fromisoformat(value)
    except ValueError as exc:
        raise ValueError(f"{field} must be YYYY-MM-DD") from exc
    if parsed.isoformat() != value:
        raise ValueError(f"{field} must be YYYY-MM-DD")
    return parsed


def _metric_claim(claim, symbol, digest, published_date, cutoff_date, page_texts):
    if not isinstance(claim, dict) or claim.get("symbol") != symbol:
        raise ValueError("claim symbol mismatch")
    metric = claim.get("metric")
    if not isinstance(metric, str) or metric not in METRIC_LABELS:
        raise ValueError("unsupported financial metric")
    if claim.get("metric_label") != METRIC_LABELS[metric]:
        raise ValueError("metric label does not match normalized metric")
    if (not isinstance(claim.get("unit"), str) or claim["unit"] not in UNITS
            or not isinstance(claim.get("period_basis"), str)
            or claim["period_basis"] not in PERIOD_BASES):
        raise ValueError("unsupported unit or period basis")
    if (not isinstance(claim.get("consolidation_scope"), str)
            or claim["consolidation_scope"] not in SCOPES):
        raise ValueError("consolidation scope required")
    for flag in ("value_verified", "source_content_verified", "official_origin_verified",
                 "historical_point_in_time_verified"):
        if flag in claim and claim[flag] is not False:
            raise ValueError("unsupported verification claim")
    if "status" in claim and claim["status"] != "manually_transcribed_unverified":
        raise ValueError("unsupported claim status")
    value = claim.get("value")
    if not isinstance(value, str) or len(value) > 60 or not _DECIMAL.fullmatch(value):
        raise ValueError("financial value must be a decimal string")
    try:
        number = Decimal(value)
    except InvalidOperation as exc:
        raise ValueError("invalid financial value") from exc
    if not number.is_finite():
        raise ValueError("invalid financial value")
    period_end = _day(claim.get("period_end"), "period_end")
    if period_end > published_date or period_end > cutoff_date:
        raise ValueError("claim period is outside publication or analysis cutoff")
    period_start = claim.get("period_start")
    if claim["period_basis"] == "period_end":
        if period_start is not None or metric != "total_assets":
            raise ValueError("period_end basis is only valid for total_assets without period_start")
    else:
        start = _day(period_start, "period_start")
        if start > period_end:
            raise ValueError("period_start is after period_end")
        if claim["period_basis"] == "year_to_date" and start != date(period_end.year, 1, 1):
            raise ValueError("year_to_date must start on January 1")
        if claim["period_basis"] == "current_quarter":
            quarter_start_month = ((period_end.month - 1) // 3) * 3 + 1
            if start != date(period_end.year, quarter_start_month, 1):
                raise ValueError("current_quarter dates do not describe one calendar quarter")
    if claim.get("source_sha256") != digest:
        raise ValueError("claim does not reference the local filing PDF")
    page = claim.get("page")
    if type(page) is not int or not 1 <= page <= 10000:
        raise ValueError("claim page must be a positive 1-based page number")
    excerpt = claim.get("excerpt")
    if not isinstance(excerpt, str) or not excerpt.strip() or len(excerpt) > 2000:
        raise ValueError("manual source excerpt required")
    page_text = page_texts.get(page)
    normalize = lambda text: "".join(text.split())
    normalized_excerpt = normalize(excerpt)
    if (not isinstance(page_text, str)
            or normalized_excerpt not in normalize(page_text)
            or METRIC_LABELS[metric] not in normalized_excerpt
            or value.replace(",", "") not in normalized_excerpt.replace(",", "")):
        raise ValueError("claim excerpt not found in parsed PDF page text")
    return {
        "symbol": symbol, "metric": metric, "metric_label": METRIC_LABELS[metric],
        "value": value, "unit": claim["unit"],
        "period_basis": claim["period_basis"],
        "period_start": period_start, "period_end": period_end.isoformat(),
        "consolidation_scope": claim["consolidation_scope"], "page": page,
        "source_sha256": digest, "excerpt": excerpt,
        "value_verified": False,
    }


def build_filing_evidence_bundle(*, pdf_path, source, claims, symbol, analysis_cutoff,
                                page_text_extractor=None):
    """Bind actual PDF bytes and user-entered claims to strict time semantics."""
    if not isinstance(symbol, str) or not re.fullmatch(r"\d{6}\.(SZ|SS)", symbol):
        raise ValueError("invalid A-share symbol")
    cutoff = _timestamp(analysis_cutoff, "analysis_cutoff")
    if not isinstance(source, dict) or source.get("symbol") != symbol:
        raise ValueError("source symbol mismatch")
    for field in ("provider", "title", "source_url"):
        if not isinstance(source.get(field), str) or not source[field].strip():
            raise ValueError(f"missing source {field}")
    try:
        parsed_url = urlsplit(source["source_url"])
        parsed_url.port
    except ValueError as exc:
        raise ValueError("invalid source URL") from exc
    if (parsed_url.scheme != "https" or not parsed_url.hostname
            or parsed_url.username or parsed_url.password):
        raise ValueError("source URL must be public HTTPS")
    if source.get("provider") != "CNINFO":
        raise ValueError("only CNINFO filing URLs are supported")
    from scripts.disclosure_pdf_fetch import validate_cninfo_pdf_url
    validate_cninfo_pdf_url(source["source_url"])
    published = _timestamp(source.get("published_at"), "published_at")
    retrieved = _timestamp(source.get("retrieved_at"), "retrieved_at")
    if published > retrieved:
        raise ValueError("publication is after retrieval")
    if retrieved > cutoff:
        raise ValueError("PDF was retrieved after the analysis cutoff")
    expected = source.get("sha256")
    if not isinstance(expected, str) or not _SHA256.fullmatch(expected):
        raise ValueError("invalid source SHA-256")
    path = Path(pdf_path)
    digest = _pdf_digest(path)
    if digest != expected:
        raise ValueError("local PDF SHA-256 does not match source record")
    if not isinstance(claims, list) or not 1 <= len(claims) <= 100:
        raise ValueError("claims must contain 1 to 100 entries")
    pages = sorted({row.get("page") for row in claims if isinstance(row, dict)
                    and type(row.get("page")) is int})
    if page_text_extractor is None:
        from scripts.offline_pdf_page_text import extract_pages
        page_text_extractor = extract_pages
    try:
        extracted = page_text_extractor(path, symbol, published.date().isoformat(), pages)
    except Exception as exc:
        raise ValueError("unable to extract requested filing pages") from exc
    page_texts = {}
    for item in extracted:
        if (not isinstance(item, dict) or item.get("file_sha256") != digest
                or type(item.get("page")) is not int or item["page"] not in pages
                or not isinstance(item.get("text"), str)
                or item["page"] in page_texts):
            raise ValueError("invalid parsed PDF page evidence")
        page_texts[item["page"]] = item["text"]
    if set(page_texts) != set(pages):
        raise ValueError("parsed PDF page evidence is incomplete")
    normalized = [_metric_claim(row, symbol, digest, published.date(), cutoff.date(), page_texts)
                  for row in claims]
    identities = [(row["metric"], row["period_basis"], row["period_start"],
                   row["period_end"], row["unit"], row["consolidation_scope"], row["page"])
                  for row in normalized]
    if len(set(identities)) != len(identities):
        raise ValueError("duplicate metric evidence location")
    return {
        "schema_version": "0.1", "symbol": symbol,
        "analysis_cutoff": cutoff.isoformat(),
        "source": {
            "provider": source["provider"], "title": source["title"],
            "source_url": source["source_url"],
            "published_at": published.isoformat(), "retrieved_at": retrieved.isoformat(),
            "sha256": digest,
        },
        "claims": normalized,
        "status": "PENDING_MANUAL_VERIFICATION",
        "official_origin_verified": False,
        "source_content_verified": False,
        "historical_point_in_time_verified": False,
        "limitations": [
            "Hash equality binds the local file bytes but does not authenticate the publisher.",
            "Claim text and metric meaning are manually transcribed and unverified.",
            "A timestamp supplied in the source record is not independently verified.",
        ],
    }
