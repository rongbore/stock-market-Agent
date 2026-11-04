"""Offline checks of supplied PDF page text; never claims PDF authenticity."""
import re

from scripts.financial_claim_evidence import validate_claims


# Conservative lexical hints only. Not financial statement interpretation.
METRIC_LABELS = {
    "revenue": ("营业收入",),
    "net_profit_attributable": ("归属于上市公司股东的净利润", "归母净利润"),
    "total_assets": ("资产总计", "总资产"),
    "operating_cash_flow": ("经营活动产生的现金流量净额",),
}


def _label_near_value(text, metric, value):
    """Only same-line label preceding the number within 80 characters."""
    token = re.compile(r"(?<![0-9.])" + re.escape(value) + r"(?![0-9.])")
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
    token = re.compile(r"(?<![0-9.])" + re.escape(value) + r"(?![0-9.])")
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
    token = re.compile(r"(?<![0-9.])" + re.escape(value) + r"(?![0-9.])")
    for line in text.splitlines():
        for match in token.finditer(line):
            prefix = line[max(0, match.start() - 80):match.start()]
            if any(re.search(r"(?<![0-9])" + re.escape(form) + r"(?![0-9])", prefix)
                   for form in date_forms):
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
        if text is None:
            status = "page_text_missing"
        else:
            # Standalone decimal tokens only: avoid matching 123 within 1234.
            value = re.escape(claim["value"])
            matched = re.search(r"(?<![0-9.])" + value + r"(?![0-9.])", text)
            status = "literal_value_found_unverified" if matched else "literal_value_not_found"
            if matched:
                label_near_value = _label_near_value(text, claim["metric"], claim["value"])
                unit_near_value = _unit_near_value(text, claim["unit"], claim["value"])
                period_near_value = _period_near_value(text, claim["period_end"], claim["value"])
        results.append({
            "metric": claim["metric"], "file_sha256": claim["file_sha256"],
            "page": claim["page"], "status": status,
            "metric_label_near_value_unverified": label_near_value,
            "unit_label_near_value_unverified": unit_near_value,
            "period_end_near_value_unverified": period_near_value,
            "pdf_text_extraction_verified": False,
            "financial_meaning_verified": False,
            "official_origin_verified": False,
        })
    return results
