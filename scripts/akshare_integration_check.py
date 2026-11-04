"""Offline-safe AKShare integration diagnostics, without leaking request data."""
import argparse
import json
import platform
import sys
import traceback
from datetime import datetime, timezone
from pathlib import Path

from scripts.akshare_provider import fetch_a_share_daily


def run(symbol, start_date, end_date, output):
    report = {
        "schema_version": "0.1",
        "status": "failed",
        "symbol": symbol,
        "start_date": start_date,
        "end_date": end_date,
        "python_version": platform.python_version(),
        "collected_at": datetime.now(timezone.utc).isoformat(),
        "akshare_version": "not_installed",
        "source_content_verified": False,
        "historical_point_in_time_verified": False,
    }
    try:
        import akshare
        report["akshare_version"] = str(getattr(akshare, "__version__", "unknown"))
        result = fetch_a_share_daily(symbol, start_date, end_date)
        if not result["records"]:
            raise ValueError("No daily records returned")
        Path(output).write_text(
            json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )
        report["status"] = "success"
        report["record_count"] = len(result["records"])
        report["first_date"] = result["records"][0]["date"]
        report["last_date"] = result["records"][-1]["date"]
    except Exception as exc:
        # No URLs, headers, response bodies, tokens, or upstream tracebacks in artifacts.
        report["error_type"] = type(exc).__name__
        report["error_summary"] = "AKShare import or public data retrieval failed; inspect restricted job logs"
    return report


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument("--symbol", default="000776.SZ")
    parser.add_argument("--start-date", required=True)
    parser.add_argument("--end-date", required=True)
    parser.add_argument("--output", default="akshare_daily_snapshot.json")
    parser.add_argument("--diagnostics", default="akshare_diagnostics.json")
    args = parser.parse_args(argv)
    report = run(args.symbol, args.start_date, args.end_date, args.output)
    Path(args.diagnostics).write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print("AKShare integration status:", report["status"])
    print("AKShare version:", report["akshare_version"])
    print("Diagnostics:", args.diagnostics)
    if report["status"] != "success":
        print("AKShare error type:", report.get("error_type", "unknown"), file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
