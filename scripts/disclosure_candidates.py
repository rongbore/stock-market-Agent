"""Offline disclosure candidate screening; no fetches and no provenance claims."""
import json
from pathlib import Path

if __package__:
    from .cn_disclosures import historical_disclosure_eligibility
else:
    from cn_disclosures import historical_disclosure_eligibility


def screen_disclosures(records, *, analysis_date, symbol):
    if not isinstance(records, list):
        raise ValueError("disclosures must be a list")
    if not isinstance(symbol, str) or not symbol.strip():
        raise ValueError("symbol required")
    normalized_symbol = symbol.strip().upper()
    candidates = []
    for item in records:
        decision = historical_disclosure_eligibility(item, analysis_date=analysis_date)
        item_symbol = item["symbol"].strip().upper()
        if item_symbol != normalized_symbol:
            raise ValueError("disclosure symbol mismatch")
        candidates.append({
            "symbol": item_symbol,
            "title": item["title"].strip(),
            "provider": item["provider"].strip(),
            "url": item["url"],
            "announcement_date": item["announcement_date"],
            **decision,
        })
    return {
        "schema_version": "0.1",
        "analysis_date": analysis_date,
        "symbol": normalized_symbol,
        "candidates": candidates,
        "source_content_verified": False,
        "historical_point_in_time_verified": False,
        "limitations": [
            "Candidate screening is not independent verification of source authenticity.",
            "No candidate is automatically eligible for the verified evidence bundle.",
            "Same-day announcements require independent publication-time verification.",
        ],
    }


def save_disclosure_candidates(directory, result):
    path = Path(directory) / "disclosure_candidates.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return path


def main():
    import argparse
    parser = argparse.ArgumentParser(description="Screen offline A-share disclosure metadata")
    parser.add_argument("input_json", help="Locally supplied JSON list; no network access")
    parser.add_argument("--analysis-date", required=True)
    parser.add_argument("--symbol", required=True)
    parser.add_argument("--output-dir", required=True)
    args = parser.parse_args()
    records = json.loads(Path(args.input_json).read_text(encoding="utf-8"))
    result = screen_disclosures(records, analysis_date=args.analysis_date, symbol=args.symbol)
    print(save_disclosure_candidates(args.output_dir, result))


if __name__ == "__main__":
    main()
