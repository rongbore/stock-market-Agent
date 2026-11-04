"""Scope PDF column hints to explicitly supplied table rectangles.

Regions are caller-provided review hints, not automatically detected tables.
"""
from scripts.financial_pdf_geometry import inspect_spans
from scripts.financial_pdf_column_hints import column_proximity_hints


def scoped_column_hints(numbers, headers, regions):
    """Return unverified hints only when both number and headers share one region."""
    inspect_spans(numbers)
    inspect_spans(headers)
    inspect_spans(regions)
    if any(region["text"] != "" for region in regions):
        raise ValueError("table regions must have empty text")
    if len(regions) > 100:
        raise ValueError("too many table regions")

    def containing_regions(span):
        page, (x0, y0, x1, y1) = span["page"], span["bbox"]
        return [
            i for i, region in enumerate(regions)
            if region["page"] == page
            and region["bbox"][0] <= x0 <= x1 <= region["bbox"][2]
            and region["bbox"][1] <= y0 <= y1 <= region["bbox"][3]
        ]

    candidates = []
    for number in numbers:
        matches = containing_regions(number)
        if len(matches) != 1:
            candidates.append({
                "page": number["page"], "text": number["text"],
                "bbox": number["bbox"], "nearest_header_hint_unverified": None,
                "reason": "number_outside_or_overlapping_regions",
                "column_ownership_verified": False,
            })
            continue
        region_index = matches[0]
        scoped_headers = [
            header for header in headers
            if containing_regions(header) == [region_index]
        ]
        result = column_proximity_hints([number], scoped_headers)
        candidate = result["candidates"][0]
        candidate["region_index_unverified"] = region_index
        candidates.append(candidate)
    return {
        "candidates": candidates,
        "column_ownership_verified": False,
        "table_boundaries_verified": False,
        "financial_meaning_verified": False,
        "note": "Regions supplied by caller; no automatic table detection.",
    }
