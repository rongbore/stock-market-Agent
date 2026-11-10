"""Validate review-package structure and hint consistency, never financial truth."""
import argparse
from datetime import date
import json
import os
from pathlib import Path
import tempfile

from scripts.akshare_provider import _symbol
from scripts.financial_filing_evidence_bundle import METRIC_LABELS
from scripts.financial_pdf_geometry import inspect_spans
from scripts.financial_table_metric_hints import UNITS
from scripts.financial_table_period_hints import HEADERS, NUMBER
from scripts.financial_table_review_annotations import review_package_sha256

FLAGS = {"official_origin_verified", "source_content_verified", "financial_meaning_verified",
         "column_ownership_verified", "historical_point_in_time_verified"}


def _cell(cell, pages):
    if not isinstance(cell, dict) or set(cell) != {
            "page", "table_index", "row_index", "column_index", "text", "bbox"}:
        raise ValueError("invalid evidence cell fields")
    inspect_spans([cell])
    for key, limit in (("table_index", 20), ("row_index", 500), ("column_index", 100)):
        if type(cell[key]) is not int or not 0 <= cell[key] < limit:
            raise ValueError("invalid evidence cell position")
    if cell["page"] not in pages or not 0 <= cell["bbox"][0] < cell["bbox"][2] or not 0 <= cell["bbox"][1] < cell["bbox"][3]:
        raise ValueError("invalid evidence page or rectangle")
    return tuple(cell[key] for key in ("page", "table_index", "row_index", "column_index"))


def validate_table_review_package(package):
    """Require internally consistent evidence; supplied coordinates remain untrusted."""
    digest = review_package_sha256(package)
    required = FLAGS | {"schema_version", "symbol", "announcement_date_supplied_unverified",
                        "file_sha256", "pages", "status", "candidate_count", "review_blockers", "candidates"}
    if set(package) != required or any(package.get(flag) is not False for flag in FLAGS):
        raise ValueError("invalid package fields or verification flags")
    _symbol(package["symbol"])
    supplied_date = package["announcement_date_supplied_unverified"]
    if not isinstance(supplied_date, str) or date.fromisoformat(supplied_date).isoformat() != supplied_date:
        raise ValueError("invalid supplied announcement date")
    pages = package["pages"]
    if (not isinstance(pages, list) or not 1 <= len(pages) <= 20
            or any(type(page) is not int or not 1 <= page <= 10000 for page in pages)
            or len(set(pages)) != len(pages)):
        raise ValueError("invalid requested pages")
    expected = (["no_numeric_candidates"] if not package["candidates"] else []) + ["consolidation_scope", "manual_verification"]
    if package["review_blockers"] != expected:
        raise ValueError("package blockers mismatch")
    seen = set()
    for candidate in package["candidates"]:
        if not isinstance(candidate, dict) or set(candidate) != {
                "cell", "header_cell", "period_hint_unverified", "reason", "column_ownership_verified",
                "metric_hint_unverified", "unit_hint_unverified", "label_cells", "metric_reason",
                "value_verified", "review_blockers", "consolidation_scope"}:
            raise ValueError("invalid candidate fields")
        cell = candidate["cell"]
        position = _cell(cell, pages)
        if position in seen or NUMBER.fullmatch(cell["text"]) is None:
            raise ValueError("duplicate or nonnumeric candidate")
        seen.add(position)
        if (candidate["column_ownership_verified"] is not False or candidate["value_verified"] is not False
                or candidate["consolidation_scope"] is not None):
            raise ValueError("candidate must remain unverified with unknown scope")
        period, header = candidate["period_hint_unverified"], candidate["header_cell"]
        if period is None:
            if header is not None or candidate["reason"] != "missing_or_ambiguous_header":
                raise ValueError("missing period evidence mismatch")
        else:
            header_position = _cell(header, pages)
            center = (cell["bbox"][0] + cell["bbox"][2]) / 2
            if (HEADERS.get(header["text"]) != period or header_position[:2] != position[:2]
                    or header["row_index"] >= cell["row_index"] or header["bbox"][3] > cell["bbox"][1]
                    or not header["bbox"][0] < center < header["bbox"][2]
                    or candidate["reason"] != "unique_header_rectangle"):
                raise ValueError("period header evidence mismatch")
        metric, unit, labels = (candidate[key] for key in
                                ("metric_hint_unverified", "unit_hint_unverified", "label_cells"))
        if metric is None:
            if unit is not None or labels != [] or candidate["metric_reason"] != "missing_or_ambiguous_row_label":
                raise ValueError("missing metric evidence mismatch")
        else:
            if (not isinstance(metric, str) or metric not in METRIC_LABELS or unit not in UNITS.values()
                    or not isinstance(labels, list) or not 1 <= len(labels) <= 4):
                raise ValueError("invalid metric or unit hint")
            for offset, label in enumerate(labels):
                label_position = _cell(label, pages)
                if (label_position[:2] != position[:2] or label["row_index"] != cell["row_index"] + offset
                        or label["column_index"] != labels[0]["column_index"]
                        or label["bbox"][2] > cell["bbox"][0]):
                    raise ValueError("metric label geometry mismatch")
            text = "".join("".join(label["text"].split()) for label in labels).replace("（", "(").replace("）", ")")
            unit_label = next(label for label, normalized in UNITS.items() if normalized == unit)
            if text != METRIC_LABELS[metric] + "(" + unit_label + ")" or candidate["metric_reason"] != "exact_row_label":
                raise ValueError("metric label text or unit mismatch")
        blockers = [key for key in ("metric", "unit", "period") if candidate[key + "_hint_unverified"] is None]
        if candidate["review_blockers"] != blockers + ["consolidation_scope", "manual_verification"]:
            raise ValueError("candidate blockers mismatch")
    return {"schema_version": "0.1", "package_sha256": digest, "file_sha256": package["file_sha256"],
            "structure_valid": True, "candidate_count": len(seen), "release_evidence_accepted": False,
            "financial_meaning_verified": False, "official_origin_verified": False,
            "limitations": ["Structure and supplied hint consistency only; no PDF re-extraction or authenticity check.",
                            "Full table context, consolidation scope and financial truth remain unverified."]}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--package", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args(argv)
    output, source = Path(args.output), Path(args.package)
    if output.is_symlink() or output.resolve() == source.resolve():
        raise ValueError("output must not overwrite package")
    with source.open("rb") as stream:
        raw = stream.read(5 * 1024 * 1024 + 1)
    if len(raw) > 5 * 1024 * 1024:
        raise ValueError("package JSON too large")
    result = validate_table_review_package(json.loads(raw))
    output.parent.mkdir(parents=True, exist_ok=True)
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", dir=output.parent, delete=False) as stream:
            temporary = Path(stream.name)
            json.dump(result, stream, ensure_ascii=False, indent=2, allow_nan=False)
            stream.write("\n")
        os.replace(temporary, output)
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
