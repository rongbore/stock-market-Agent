"""Unverified horizontal header-proximity hints for PDF numeric boxes.

This is not table parsing, period attribution, or financial verification.
"""
import math

from scripts.financial_pdf_geometry import inspect_spans

HEADER_LABELS = frozenset(("本期金额", "上期金额", "本期发生额", "上期发生额", "期末余额", "期初余额"))
PAIRS = (frozenset(("本期金额", "上期金额")),
         frozenset(("本期发生额", "上期发生额")),
         frozenset(("期末余额", "期初余额")))


def column_proximity_hints(numbers, headers, max_dx=120.0, min_margin=8.0):
    """Compare x-centers only when a same-page recognized header pair is supplied."""
    if type(max_dx) not in (int, float) or not math.isfinite(max_dx) or not 0 < max_dx <= 1000:
        raise ValueError("invalid max_dx")
    if type(min_margin) not in (int, float) or not math.isfinite(min_margin) or not 0 <= min_margin <= 100:
        raise ValueError("invalid min_margin")
    inspect_spans(numbers)
    inspect_spans(headers)
    if any(h["text"] not in HEADER_LABELS for h in headers):
        raise ValueError("unsupported column header")
    result = []
    for number in numbers:
        page_headers = [h for h in headers if h["page"] == number["page"]]
        pairs = [
            (a, b) for i, a in enumerate(page_headers) for b in page_headers[i + 1:]
            if frozenset((a["text"], b["text"])) in PAIRS
        ]
        # Repeated header pairs or absent headers cannot establish a unique table context.
        hint = None
        reason = "missing_or_ambiguous_header_pair"
        if len(pairs) == 1:
            a, b = pairs[0]
            x = (number["bbox"][0] + number["bbox"][2]) / 2
            ax = (a["bbox"][0] + a["bbox"][2]) / 2
            bx = (b["bbox"][0] + b["bbox"][2]) / 2
            da, db = abs(x - ax), abs(x - bx)
            if abs(ax - bx) <= min_margin:
                reason = "header_centers_overlap"
            elif min(da, db) > max_dx:
                reason = "number_far_from_headers"
            elif abs(da - db) < min_margin:
                reason = "equidistant_from_headers"
            else:
                hint = a["text"] if da < db else b["text"]
                reason = "nearest_header_x_only_unverified"
        result.append({
            "page": number["page"], "text": number["text"],
            "bbox": number["bbox"], "nearest_header_hint_unverified": hint,
            "reason": reason, "column_ownership_verified": False,
        })
    return {"candidates": result, "column_ownership_verified": False,
            "financial_meaning_verified": False,
            "note": "X-axis proximity only; table boundaries and row/period meaning not established."}
