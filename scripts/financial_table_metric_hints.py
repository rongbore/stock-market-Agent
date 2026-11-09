"""Unverified metric/unit hints from explicit row labels, including split labels."""
import re

from scripts.financial_filing_evidence_bundle import METRIC_LABELS
from scripts.financial_table_period_hints import table_period_hints

UNITS = {"元": "CNY", "万元": "CNY_10000", "亿元": "CNY_100000000"}


def table_metric_hints(cells):
    """Combine exact label hints with period hints without promoting verification."""
    result = table_period_hints(cells)  # Validate positions, duplicates and geometry first.
    groups = {}
    for cell in cells:
        groups.setdefault((cell["page"], cell["table_index"], cell["row_index"]), []).append(cell)

    def match(text):
        text = "".join(text.split()).replace("（", "(").replace("）", ")")
        for metric, label in METRIC_LABELS.items():
            found = re.fullmatch(re.escape(label) + r"\((元|万元|亿元)\)", text)
            if found:
                return metric, UNITS[found[1]]
        return None

    for candidate in result["candidates"]:
        number = candidate["cell"]
        key = (number["page"], number["table_index"], number["row_index"])
        labels = [c for c in groups[key] if c.get("text") and c.get("bbox")
                  and c["bbox"][2] <= number["bbox"][0]]
        matches = []
        for label in labels:
            parts = [label]
            text = label["text"]
            found = match(text)
            # Only a continuation-only row in the same label column is eligible.
            for offset in (1, 2, 3):
                if found:
                    break
                row = groups.get((key[0], key[1], key[2] + offset), [])
                populated = [c for c in row if isinstance(c.get("text"), str) and c["text"].strip()]
                if (len(populated) != 1 or populated[0]["column_index"] != label["column_index"]
                        or not populated[0].get("bbox")
                        or populated[0]["bbox"][2] > number["bbox"][0]):
                    break
                parts.append(populated[0])
                text += populated[0]["text"]
                found = match(text)
            if found:
                matches.append((found, parts))
        unique = matches[0] if len(matches) == 1 else None
        candidate.update({"metric_hint_unverified": unique[0][0] if unique else None,
                          "unit_hint_unverified": unique[0][1] if unique else None,
                          "label_cells": unique[1] if unique else [],
                          "metric_reason": "exact_row_label" if unique else "missing_or_ambiguous_row_label",
                          "value_verified": False})
    return result
