"""Offline checks of supplied PDF page text; never claims PDF authenticity."""
import re

from scripts.financial_claim_evidence import validate_claims


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
        if text is None:
            status = "page_text_missing"
        else:
            # Standalone decimal tokens only: avoid matching 123 within 1234.
            value = re.escape(claim["value"])
            matched = re.search(r"(?<![0-9.])" + value + r"(?![0-9.])", text)
            status = "literal_value_found_unverified" if matched else "literal_value_not_found"
        results.append({
            "metric": claim["metric"], "file_sha256": claim["file_sha256"],
            "page": claim["page"], "status": status,
            "pdf_text_extraction_verified": False,
            "financial_meaning_verified": False,
            "official_origin_verified": False,
        })
    return results
