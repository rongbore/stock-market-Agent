"""Read-only dual-upstream smoke check with safe failure diagnostics."""
import argparse
import json
from pathlib import Path

from scripts.akshare_provider import fetch_a_share_daily
from scripts.akshare_sina_provider import fetch_sina_daily
from scripts.akshare_crosscheck import compare


def _write(folder, filename, data):
    (folder / filename).write_text(
        json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )


def run(symbol, start_date, end_date, folder, *, eastmoney=fetch_a_share_daily,
        sina=fetch_sina_daily):
    """Always produce safe stage diagnostics; preserve successful partial snapshots."""
    folder = Path(folder)
    folder.mkdir(parents=True, exist_ok=True)
    diag = {"schema_version": "0.1", "symbol": symbol,
            "start_date": start_date, "end_date": end_date,
            "status": "failed", "stage": "eastmoney",
            "eastmoney_record_count": 0, "sina_record_count": 0,
            "cross_source_numerical_agreement": False,
            "independent_source_verified": False}
    try:
        primary = eastmoney(symbol, start_date, end_date)
        if not primary.get("records"):
            raise ValueError("empty Eastmoney snapshot")
        diag["eastmoney_record_count"] = len(primary["records"])
        _write(folder, "eastmoney_daily_unverified.json", primary)
        diag["stage"] = "sina"
        secondary = sina(symbol, start_date, end_date)
        if not secondary.get("records"):
            raise ValueError("empty Sina snapshot")
        diag["sina_record_count"] = len(secondary["records"])
        _write(folder, "sina_daily_unverified.json", secondary)
        diag["stage"] = "compare"
        result = compare(primary, secondary)
        _write(folder, "daily_crosscheck_report.json", result)
        diag["cross_source_numerical_agreement"] = result["cross_source_numerical_agreement"]
        diag["status"] = "success" if result["status"] == "passed" else "mismatch"
        diag["stage"] = "complete"
        return 0 if result["status"] == "passed" else 1
    except (ValueError, TypeError, KeyError, RuntimeError, ConnectionError, TimeoutError, OSError):
        # No raw exception text, URLs, tokens, or response bodies in diagnostics.
        return 1
    finally:
        _write(folder, "dual_upstream_diagnostics.json", diag)


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument("--symbol", default="000776.SZ")
    parser.add_argument("--start-date", default="2026-10-01")
    parser.add_argument("--end-date", default="2026-10-30")
    parser.add_argument("--output-dir", default=".")
    args = parser.parse_args(argv)
    return run(args.symbol, args.start_date, args.end_date, args.output_dir)


if __name__ == "__main__":
    raise SystemExit(main())
