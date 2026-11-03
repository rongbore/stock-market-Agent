"""Validate report artifacts without invoking an LLM or accessing financial data."""
from pathlib import Path


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


def validate_reports_root(root):
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
    return errors


def main():
    import argparse
    parser = argparse.ArgumentParser(description="Check generated HTML report artifacts")
    parser.add_argument("reports_root", nargs="?", default="results/reports")
    args = parser.parse_args()
    errors = validate_reports_root(args.reports_root)
    if errors:
        for error in errors:
            print(f"ERROR: {error}")
        raise SystemExit(1)
    print("Report artifact contract passed")


if __name__ == "__main__":
    main()
