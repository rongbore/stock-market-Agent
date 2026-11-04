"""Conservative PDF drawn-rectangle table-region candidates, not verified tables."""
import math

from scripts.financial_pdf_geometry import inspect_spans


def rectangle_region_candidates(rectangles, min_width=80, min_height=30):
    """Filter supplied pdfplumber-like drawn rectangles into unverified regions."""
    if not isinstance(rectangles, list) or len(rectangles) > 2000:
        raise ValueError("rectangles must be a list of at most 2000")
    if any(type(v) not in (int, float) or not math.isfinite(v)
           or not 0 < v <= 10000 for v in (min_width, min_height)):
        raise ValueError("invalid minimum rectangle dimensions")
    regions = []
    for item in rectangles:
        if not isinstance(item, dict):
            raise ValueError("invalid rectangle record")
        page = item.get("page")
        coords = [item.get(k) for k in ("x0", "top", "x1", "bottom")]
        probe = [{"page": page, "text": "", "bbox": coords}]
        inspect_spans(probe)
        x0, top, x1, bottom = coords
        if x1 - x0 >= min_width and bottom - top >= min_height:
            regions.append(probe[0])
            if len(regions) > 100:
                raise ValueError("too many candidate table regions")
    # Multiple nested or overlapping rectangles cannot safely establish table ownership.
    ambiguous = set()
    for i, a in enumerate(regions):
        for j in range(i + 1, len(regions)):
            b = regions[j]
            if a["page"] != b["page"]:
                continue
            ax0, ay0, ax1, ay1 = a["bbox"]
            bx0, by0, bx1, by1 = b["bbox"]
            if min(ax1, bx1) > max(ax0, bx0) and min(ay1, by1) > max(ay0, by0):
                ambiguous.update((i, j))
    return {
        "regions": [r for i, r in enumerate(regions) if i not in ambiguous],
        "ambiguous_overlap_count": len(ambiguous),
        "region_candidates_unverified": True,
        "table_boundaries_verified": False,
        "financial_meaning_verified": False,
        "note": "Only explicit drawn rectangles; borderless tables are not detected.",
    }
