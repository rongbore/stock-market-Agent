"""Run a read-only AKShare A-share daily smoke test and persist unverified metadata."""
import argparse
import json
from pathlib import Path

if __package__:
    from .akshare_provider import fetch_a_share_daily
else:
    from akshare_provider import fetch_a_share_daily


def main(argv=None):
    parser = argparse.ArgumentParser(description="AKShare public daily data smoke test")
    parser.add_argument("--symbol", default="000776.SZ")
    parser.add_argument("--start-date", required=True)
    parser.add_argument("--end-date", required=True)
    parser.add_argument("--output", default="akshare_daily_snapshot.json")
    args = parser.parse_args(argv)
    output = Path(args.output)
    result = fetch_a_share_daily(args.symbol, args.start_date, args.end_date)
    if not result["records"]:
        raise RuntimeError("No daily records returned; upstream not verified")
    if output.exists():
        raise FileExistsError("Refusing to overwrite an existing data snapshot")
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print("AKShare records:", len(result["records"]))
    print("Date range:", result["records"][0]["date"], result["records"][-1]["date"])
    print("Snapshot:", output)
    print("Verified:", result["source_content_verified"])


if __name__ == "__main__":
    main()
