"""Validate caller-supplied PDF text positions without asserting column ownership."""
import math
import re

MAX_SPANS = 2000
MAX_TEXT = 500


def inspect_spans(spans):
    """Return bounded geometry diagnostics; coordinates are unverified caller input."""
    if not isinstance(spans, list) or len(spans) > MAX_SPANS:
        raise ValueError("spans must be a list of at most 2000")
    checked = []
    for item in spans:
        if not isinstance(item, dict):
            raise ValueError("invalid span record")
        text = item.get("text")
        page = item.get("page")
        box = item.get("bbox")
        if not isinstance(text, str) or len(text) > MAX_TEXT:
            raise ValueError("invalid span text")
        if type(page) is not int or not 1 <= page <= 10000:
            raise ValueError("invalid span page")
        if not isinstance(box, list) or len(box) != 4:
            raise ValueError("bbox must have four coordinates")
        if any(type(v) not in (int, float) or not math.isfinite(v)
               or abs(v) > 100000 for v in box):
            raise ValueError("invalid bbox coordinate")
        x0, y0, x1, y1 = box
        if x1 < x0 or y1 < y0:
            raise ValueError("inverted bbox")
        checked.append({"page": page, "text": text, "bbox": box})
    return {
        "span_count": len(checked),
        "pages": sorted({item["page"] for item in checked}),
        "geometry_supplied_unverified": bool(checked),
        "column_ownership_verified": False,
        "official_origin_verified": False,
        "financial_meaning_verified": False,
        "note": "Caller-supplied coordinates only; no PDF extraction or table column assignment.",
    }


def column_candidates(spans, page, value):
    """Find exact numeric tokens with bounding boxes; do not infer table columns."""
    inspect_spans(spans)
    if type(page) is not int or not 1 <= page <= 10000:
        raise ValueError("invalid requested page")
    if not isinstance(value, str) or not re.fullmatch(r"-?[0-9]+(?:\.[0-9]+)?", value):
        raise ValueError("invalid requested numeric value")
    token = re.compile(r"(?<![0-9.,+−-])" + re.escape(value) + r"(?![0-9.,])")
    matches = [
        {"page": page, "text": item["text"], "bbox": item["bbox"],
         "column_ownership_verified": False}
        for item in spans if item["page"] == page and token.search(item["text"])
    ]
    return {"candidates": matches, "candidate_count": len(matches),
            "column_ownership_verified": False,
            "geometry_supplied_unverified": True}
