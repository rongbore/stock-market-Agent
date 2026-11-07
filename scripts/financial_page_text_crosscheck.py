"""Offline checks of supplied PDF page text; never claims PDF authenticity."""
import re
from datetime import date, datetime

from scripts.financial_claim_evidence import validate_claims
from scripts.disclosure_pdf_fetch import validate_cninfo_pdf_url


# Conservative lexical hints only. Not financial statement interpretation.
METRIC_LABELS = {
    "revenue": ("营业收入",),
    "net_profit_attributable": ("归属于上市公司股东的净利润", "归母净利润"),
    "total_assets": ("资产总计", "总资产"),
    "operating_cash_flow": ("经营活动产生的现金流量净额",),
}


def _number_token(value):
    """Avoid treating a positive value as part of a signed or grouped number."""
    return re.compile(r"(?<![0-9.,+−-])" + re.escape(value) + r"(?![0-9.,])")


def _label_near_value(text, metric, value):
    """Only same-line label preceding the number within 80 characters."""
    token = _number_token(value)
    labels = METRIC_LABELS[metric]
    for line in text.splitlines():
        for match in token.finditer(line):
            prefix = line[max(0, match.start() - 80):match.start()]
            if any(label in prefix for label in labels):
                return True
    return False



# Exact, same-line unit markers; no inference from report-wide headings.
UNIT_LABELS = {
    "CNY": ("人民币元",),
    "CNY_10000": ("万元",),
    "CNY_100000000": ("亿元",),
}


def _unit_near_value(text, unit, value):
    """A unit marker immediately before or after a number, same line only."""
    token = _number_token(value)
    for line in text.splitlines():
        for match in token.finditer(line):
            prefix = line[max(0, match.start() - 12):match.start()].rstrip()
            suffix = line[match.end():match.end() + 12].lstrip()
            if any(prefix.endswith(label) or suffix.startswith(label)
                   for label in UNIT_LABELS[unit]):
                return True
    return False


def _period_near_value(text, period_end, value):
    """Same-line date before number within 80 characters; weak hint only."""
    year, month, day = (int(part) for part in period_end.split("-"))
    date_forms = (
        period_end,
        f"{year}年{month}月{day}日",
        f"{year}年{month:02d}月{day:02d}日",
    )
    token = _number_token(value)
    for line in text.splitlines():
        for match in token.finditer(line):
            prefix = line[max(0, match.start() - 80):match.start()]
            if any(re.search(r"(?<![0-9])" + re.escape(form) + r"(?![0-9])", prefix)
                   for form in date_forms):
                return True
    return False



# Detect only obvious multi-column financial table headings, never resolve a column.
COLUMN_HEADER_PAIRS = (
    ("本期金额", "上期金额"),
    ("本期发生额", "上期发生额"),
    ("期末余额", "期初余额"),
    ("本报告期", "上年同期"),
)


def _table_column_ambiguous(text, value):
    """Conservative page-level warning: headings plus multiple row numbers."""
    if not any(left in text and right in text
               for left, right in COLUMN_HEADER_PAIRS):
        return False
    token = re.compile(r"(?<![0-9.\-])" + re.escape(value) + r"(?![0-9.])")
    for line in text.splitlines():
        if not token.search(line):
            continue
        numbers = re.findall(r"(?<![0-9.])\-?[0-9]+(?:\.[0-9]+)?(?![0-9.])", line)
        if len(numbers) >= 2:
            return True
    return False


def check_page_text(claims, fingerprints, pages, symbol, research_date):
    """Compare claims with caller-supplied page text, not independently extracted PDF."""
    validated = validate_claims(claims, fingerprints, symbol, research_date)
    if not isinstance(pages, list) or len(pages) > 100:
        raise ValueError("pages must be a list of at most 100")
    lookup = {}
    for item in pages:
        if not isinstance(item, dict):
            raise ValueError("invalid page record")
        digest, page, text = item.get("file_sha256"), item.get("page"), item.get("text")
        if not isinstance(digest, str) or not re.fullmatch(r"[0-9a-f]{64}", digest):
            raise ValueError("invalid page SHA-256")
        if isinstance(page, bool) or not isinstance(page, int) or not 1 <= page <= 10000:
            raise ValueError("invalid page number")
        if not isinstance(text, str) or len(text) > 100000:
            raise ValueError("invalid page text")
        key = (digest, page)
        if key in lookup:
            raise ValueError("duplicate page record")
        lookup[key] = text
    results = []
    for claim in validated:
        text = lookup.get((claim["file_sha256"], claim["page"]))
        label_near_value = False
        unit_near_value = False
        period_near_value = False
        column_ambiguous = False
        if text is None:
            status = "page_text_missing"
        else:
            # Standalone decimal tokens only: avoid matching 123 within 1234.
            matched = _number_token(claim["value"]).search(text)
            status = "literal_value_found_unverified" if matched else "literal_value_not_found"
            if matched:
                label_near_value = _label_near_value(text, claim["metric"], claim["value"])
                unit_near_value = _unit_near_value(text, claim["unit"], claim["value"])
                period_near_value = _period_near_value(text, claim["period_end"], claim["value"])
                column_ambiguous = _table_column_ambiguous(text, claim["value"])
        results.append({
            "metric": claim["metric"], "file_sha256": claim["file_sha256"],
            "page": claim["page"], "status": status,
            "metric_label_near_value_unverified": label_near_value,
            "unit_label_near_value_unverified": unit_near_value,
            "period_end_near_value_unverified": period_near_value,
            "table_column_ambiguous_unverified": column_ambiguous,
            "pdf_text_extraction_verified": False,
            "financial_meaning_verified": False,
            "official_origin_verified": False,
        })
    return results


def check_disclosure_page_evidence(claims, fingerprints, evidence, symbol, research_date):
    """Cross-check claims against page evidence exported from a disclosure snapshot.

    This validates the evidence links and literal text only. It does not prove
    that the PDF came from CNINFO, that the document is authentic, or that a
    number belongs to the named metric or period.
    """
    if (not isinstance(evidence, dict) or evidence.get("schema_version") != "0.1"
            or evidence.get("all_pages_verified") is not False):
        raise ValueError("invalid or verified disclosure page evidence")
    records = evidence.get("pages")
    if (not isinstance(records, list) or len(records) > 100
            or type(evidence.get("page_count")) is not int
            or evidence["page_count"] != len(records)):
        raise ValueError("invalid disclosure page evidence collection")

    pages, citation_by_page = [], {}
    for item in records:
        if not isinstance(item, dict):
            raise ValueError("invalid disclosure page evidence")
        item_symbol = item.get("symbol")
        raw_date = item.get("announcement_date")
        url = item.get("source_url")
        retrieved = item.get("retrieved_at")
        digest, page, text = item.get("file_sha256"), item.get("page"), item.get("text")
        if item_symbol != symbol:
            raise ValueError("disclosure page evidence symbol mismatch")
        if not isinstance(raw_date, str):
            raise ValueError("disclosure page announcement date required")
        try:
            parsed_date = date.fromisoformat(raw_date)
        except ValueError as exc:
            raise ValueError("invalid disclosure page announcement date") from exc
        if parsed_date.isoformat() != raw_date:
            raise ValueError("invalid disclosure page announcement date")
        if not isinstance(url, str):
            raise ValueError("disclosure source URL required")
        try:
            validate_cninfo_pdf_url(url)
        except ValueError as exc:
            raise ValueError("disclosure source URL must be CNINFO finalpage HTTPS") from exc
        if not isinstance(retrieved, str):
            raise ValueError("disclosure retrieval timestamp required")
        try:
            retrieved_at = datetime.fromisoformat(retrieved.replace("Z", "+00:00"))
        except ValueError as exc:
            raise ValueError("invalid disclosure retrieval timestamp") from exc
        if retrieved_at.tzinfo is None or retrieved_at.utcoffset() is None:
            raise ValueError("disclosure retrieval timestamp needs a timezone")
        if not isinstance(digest, str) or not re.fullmatch(r"[0-9a-f]{64}", digest):
            raise ValueError("invalid disclosure page SHA-256")
        if isinstance(page, bool) or not isinstance(page, int) or not 1 <= page <= 10000:
            raise ValueError("invalid disclosure page number")
        if not isinstance(text, str) or len(text) > 100000:
            raise ValueError("invalid disclosure page text")
        for field in ("official_origin_verified", "source_content_verified",
                      "financial_meaning_verified", "historical_point_in_time_verified"):
            if item.get(field) is not False:
                raise ValueError("disclosure page evidence must remain unverified")
        key = (digest, page)
        if key in citation_by_page:
            raise ValueError("duplicate disclosure page citation")
        citation_by_page[key] = {
            "source_url": url, "retrieved_at": retrieved,
            "announcement_date": raw_date,
        }
        pages.append({"file_sha256": digest, "page": page, "text": text})

    checked = check_page_text(claims, fingerprints, pages, symbol, research_date)
    validated_claims = validate_claims(claims, fingerprints, symbol, research_date)
    result = []
    for claim, item in zip(validated_claims, checked):
        citation = citation_by_page.get((claim["file_sha256"], claim["page"]))
        if citation is not None and citation["announcement_date"] != claim["announcement_date"]:
            raise ValueError("page announcement date differs from financial claim")
        retrieved_date = (date.fromisoformat(citation["retrieved_at"][:10])
                          if citation else None)
        research_day = date.fromisoformat(research_date)
        result.append({
            **item,
            "source_url": citation["source_url"] if citation else None,
            "retrieved_at": citation["retrieved_at"] if citation else None,
            "retrieval_date_after_research_date": bool(
                retrieved_date and retrieved_date > research_day),
            "source_url_match_verified": False,
            "historical_point_in_time_verified": False,
        })
    return result
