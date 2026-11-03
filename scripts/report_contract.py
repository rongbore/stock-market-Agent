"""Validate report artifacts without invoking an LLM or accessing financial data."""
import json
from pathlib import Path

if __package__:
    from .evidence_bundle import validate_evidence_bundle
else:
    from evidence_bundle import validate_evidence_bundle


def validate_report_directory(directory):
    """Return a list of problems; an empty list means required HTML exists."""
    report_dir = Path(directory)
    report = report_dir / "complete_report.html"
    errors = []
    if not report.is_file():
        return ["missing complete_report.html"]
    if report.stat().st_size == 0:
        errors.append("complete_report.html is empty")
    else:
        text = report.read_text(encoding="utf-8", errors="replace")
        if not text.strip():
            errors.append("complete_report.html contains only whitespace")
        if "<html" not in text.lower():
            errors.append("complete_report.html has no html root tag")
    return errors


def validate_report_metadata(directory):
    """Require internally consistent run metadata and explicit evidence limitations."""
    directory = Path(directory)
    errors = []
    payloads = {}
    for filename in ("run_provenance.json", "evidence_bundle.json"):
        path = directory / filename
        if not path.is_file():
            errors.append(f"missing {filename}")
            continue
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
            if not isinstance(payload, dict):
                raise ValueError("not an object")
            payloads[filename] = payload
        except (ValueError, OSError, UnicodeError):
            errors.append(f"invalid {filename}")
    if len(payloads) != 2:
        return errors
    run = payloads["run_provenance.json"]
    evidence = payloads["evidence_bundle.json"]
    if not isinstance(run.get("analysis_date"), str) or run["analysis_date"] != evidence.get("analysis_date"):
        errors.append("analysis_date mismatch between provenance and evidence")
    if run.get("market_data_sources_verified") is not False:
        errors.append("run must not claim verified market data")
    if evidence.get("source_content_verified") is not False:
        errors.append("evidence must not claim verified source content")
    if evidence.get("historical_point_in_time_verified") is not False:
        errors.append("evidence must not claim verified historical availability")
    if not isinstance(run.get("source_records"), list) or not isinstance(evidence.get("records"), list):
        errors.append("source record fields must be lists")
    elif run["source_records"] != evidence["records"]:
        errors.append("source records differ between manifest and evidence")
    if isinstance(evidence.get("records"), list) and isinstance(run.get("analysis_date"), str):
        try:
            expected = validate_evidence_bundle(
                evidence["records"],
                analysis_date=run["analysis_date"],
                cutoff=evidence.get("analysis_cutoff"),
            )
            if evidence.get("analysis_cutoff") != expected["analysis_cutoff"]:
                errors.append("evidence analysis cutoff is inconsistent")
            if evidence.get("metadata_validated") is not True:
                errors.append("evidence metadata validation marker is missing")
        except (ValueError, TypeError, OverflowError):
            errors.append("evidence records or cutoff failed validation")
    return errors


def validate_reports_root(root, *, require_metadata=False):
    """Ensure at least one generated report directory has valid HTML."""
    root = Path(root)
    if not root.is_dir():
        return ["reports directory is missing"]
    candidates = list(root.rglob("complete_report.html"))
    if not candidates:
        return ["no complete_report.html found in reports directory"]
    errors = []
    for candidate in candidates:
        errors.extend(f"{candidate}: {error}" for error in
                      validate_report_directory(candidate.parent))
        if require_metadata:
            errors.extend(f"{candidate}: {error}" for error in
                          validate_report_metadata(candidate.parent))
    return errors


def main():
    import argparse
    parser = argparse.ArgumentParser(description="Check generated HTML report artifacts")
    parser.add_argument("reports_root", nargs="?", default="results/reports")
    parser.add_argument("--require-metadata", action="store_true",
                        help="Require consistent provenance and evidence bundle")
    args = parser.parse_args()
    errors = validate_reports_root(args.reports_root, require_metadata=args.require_metadata)
    if errors:
        for error in errors:
            print(f"ERROR: {error}")
        raise SystemExit(1)
    print("Report artifact contract passed")


if __name__ == "__main__":
    main()
