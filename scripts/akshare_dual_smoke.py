"""Read-only dual-upstream smoke check; produces an explicit comparison report."""
import argparse
import json
from pathlib import Path

from scripts.akshare_provider import fetch_a_share_daily
from scripts.akshare_sina_provider import fetch_sina_daily
from scripts.akshare_crosscheck import compare


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument("--symbol", default="000776.SZ")
    parser.add_argument("--start-date", default="2026-10-01")
    parser.add_argument("--end-date", default="2026-10-30")
    parser.add_argument("--output-dir", default=".")
    args = parser.parse_args(argv)
    folder = Path(args.output_dir)
    folder.mkdir(parents=True, exist_ok=True)
    primary = fetch_a_share_daily(args.symbol, args.start_date, args.end_date)
    secondary = fetch_sina_daily(args.symbol, args.start_date, args.end_date)
    if not primary["records"] or not secondary["records"]:
        raise ValueError("empty result from either upstream")
    result = compare(primary, secondary)
    for filename, data in (
        ("eastmoney_daily_unverified.json", primary),
        ("sina_daily_unverified.json", secondary),
        ("daily_crosscheck_report.json", result),
    ):
        (folder / filename).write_text(
            json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )
    print("Dual-upstream status:", result["status"],
          "differences:", result["difference_count"])
    return 0 if result["status"] == "passed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
