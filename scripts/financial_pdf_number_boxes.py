"""Conservative number assembly from extracted PDF single-character boxes.

Geometry is an unverified text-extraction hint, never a financial column verdict.
"""
import re

from scripts.financial_pdf_geometry import inspect_spans

# Group punctuation with digits so a partial number cannot be mistaken for a claim.
NUMERIC_CHARS = frozenset("0123456789.,+-−")
DECIMAL = re.compile(r"-?[0-9]+(?:\\.[0-9]+)?\\Z")


def number_boxes(spans, max_gap=3.0, max_y_delta=2.0):
    """Return contiguous numeric runs with bounding boxes; no cross-line joins."""
    inspect_spans(spans)
    if type(max_gap) not in (int, float) or not 0 <= max_gap <= 20:
        raise ValueError("invalid max_gap")
    if type(max_y_delta) not in (int, float) or not 0 <= max_y_delta <= 20:
        raise ValueError("invalid max_y_delta")
    # Only single characters: multi-character spans have unknown per-character boxes.
    chars = [s for s in spans if len(s["text"]) == 1]
    chars.sort(key=lambda s: (s["page"], s["bbox"][1], s["bbox"][0]))
    runs = []
    current = []

    def flush():
        if not current:
            return
        token = "".join(c["text"] for c in current)
        if DECIMAL.fullmatch(token):
            runs.append({
                "page": current[0]["page"], "text": token,
                "bbox": [
                    min(c["bbox"][0] for c in current),
                    min(c["bbox"][1] for c in current),
                    max(c["bbox"][2] for c in current),
                    max(c["bbox"][3] for c in current),
                ],
                "column_ownership_verified": False,
            })

    for char in chars:
        if char["text"] not in NUMERIC_CHARS:
            flush()
            current = []
            continue
        if current:
            previous = current[-1]
            same_line = (char["page"] == previous["page"] and
                         abs(char["bbox"][1] - previous["bbox"][1]) <= max_y_delta)
            gap = char["bbox"][0] - previous["bbox"][2]
            if not same_line or not -0.5 <= gap <= max_gap:
                flush()
                current = []
        current.append(char)
    flush()
    return {
        "numbers": runs,
        "number_count": len(runs),
        "geometry_assembled_unverified": True,
        "column_ownership_verified": False,
        "financial_meaning_verified": False,
    }
