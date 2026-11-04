"""Deterministic quality checks for unverified read-only A-share daily snapshots."""
import argparse
import json
import math
from datetime import date
from pathlib import Path


def check_snapshot(snapshot):
    errors = []
    rows = snapshot.get("records")
    if not isinstance(rows, list) or not rows:
        return {"status": "failed", "errors": ["records must be nonempty"], "record_count": 0}
    if snapshot.get("source") != "akshare" or snapshot.get("interface") != "stock_zh_a_hist":
        errors.append("unexpected source or interface")
    if snapshot.get("adjust") not in ("", "qfq", "hfq"):
        errors.append("invalid adjustment mode")
    if snapshot.get("source_content_verified") is not False:
        errors.append("source verification must remain false")
    if snapshot.get("historical_point_in_time_verified") is not False:
        errors.append("point-in-time verification must remain false")
    try:
        start = date.fromisoformat(snapshot["start_date"])
        end = date.fromisoformat(snapshot["end_date"])
        if start > end:
            errors.append("reversed date range")
    except (KeyError, TypeError, ValueError):
        errors.append("invalid date range")
        start = end = None
    dates = set()
    for i, row in enumerate(rows):
        try:
            day = date.fromisoformat(row["date"])
            if day in dates:
                errors.append(f"duplicate date at row {i}")
            dates.add(day)
            if start and not start <= day <= end:
                errors.append(f"date outside requested range at row {i}")
            if day.weekday() >= 5:
                errors.append(f"weekend date at row {i}")
            values = [row[k] for k in ("open", "high", "low", "close", "volume")]
            if any(isinstance(v, bool) or not isinstance(v, (int, float))
                   or not math.isfinite(v) for v in values):
                raise ValueError("invalid numeric field")
            op, hi, lo, cl, volume = values
            if min(op, cl) < lo or max(op, cl) > hi or lo < 0 or volume < 0:
                errors.append(f"inconsistent OHLCV at row {i}")
        except (KeyError, TypeError, ValueError):
            errors.append(f"invalid row at index {i}")
    if len(dates) != len(rows):
        errors.append("nonunique dates")
    return {
        "schema_version": "0.1",
        "status": "passed" if not errors else "failed",
        "symbol": snapshot.get("symbol"),
        "record_count": len(rows),
        "date_count": len(dates),
        "price_unit": "CNY_per_share",
        "volume_unit": "lots_100_shares",
        "adjust": snapshot.get("adjust"),
        "independent_source_verified": False,
        "errors": errors,
    }


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", required=True)
    parser.add_argument("--report", required=True)
    args = parser.parse_args(argv)
    snapshot = json.loads(Path(args.input).read_text(encoding="utf-8"))
    report = check_snapshot(snapshot)
    Path(args.report).write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print("Snapshot quality:", report["status"], "records:", report["record_count"])
    return 0 if report["status"] == "passed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
