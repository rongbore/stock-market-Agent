"""Offline cross-check of two independently sourced daily OHLCV snapshots.

The second snapshot must be acquired separately; this tool never claims independence
merely because a second file exists. No market requests or trading operations.
"""
import argparse
import json
import math
from datetime import date
from pathlib import Path


FIELDS = ("open", "high", "low", "close", "volume")


def _rows(snapshot):
    """Validate offline records before accepting any numerical agreement."""
    try:
        start = date.fromisoformat(snapshot["start_date"])
        end = date.fromisoformat(snapshot["end_date"])
        if start.isoformat() != snapshot["start_date"] or end.isoformat() != snapshot["end_date"] or start > end:
            raise ValueError("invalid snapshot date window")
    except (KeyError, TypeError, ValueError) as exc:
        raise ValueError("invalid snapshot date window") from exc
    records = snapshot.get("records")
    if not isinstance(records, list) or not 0 < len(records) <= 100000:
        raise ValueError("invalid snapshot record count")
    result = {}
    for row in records:
        if not isinstance(row, dict):
            raise ValueError("invalid snapshot row")
        day = row.get("date")
        if not isinstance(day, str):
            raise ValueError("invalid trading date")
        try:
            parsed = date.fromisoformat(day)
        except ValueError as exc:
            raise ValueError("invalid trading date") from exc
        if parsed.isoformat() != day or not start <= parsed <= end:
            raise ValueError("out-of-range trading date")
        if day in result:
            raise ValueError("duplicate trading date")
        for field in FIELDS:
            value = row.get(field)
            if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value) or value < 0:
                raise ValueError("invalid nonnegative OHLCV value")
        if row["low"] > min(row["open"], row["close"]) or row["high"] < max(row["open"], row["close"]) or row["high"] < row["low"]:
            raise ValueError("inconsistent OHLC")
        result[day] = row
    return result


def compare(primary, secondary, price_tolerance=0.011, volume_tolerance=0.001):
    if primary.get("symbol") != secondary.get("symbol"):
        raise ValueError("symbol mismatch")
    if primary.get("adjust") != secondary.get("adjust"):
        raise ValueError("adjustment mode mismatch")
    if primary.get("start_date") != secondary.get("start_date") or primary.get("end_date") != secondary.get("end_date"):
        raise ValueError("date window mismatch")
    first = _rows(primary)
    second = _rows(secondary)
    # Provider independence is a provenance claim, not a guess based on filenames.
    independent = bool(primary.get("upstream") and secondary.get("upstream")
                       and primary["upstream"] != secondary["upstream"])
    punit = primary.get("volume_unit")
    sunit = secondary.get("volume_unit")
    if punit not in ("lots_100_shares", "shares") or sunit not in ("lots_100_shares", "shares"):
        raise ValueError("explicit volume units required for both snapshots")
    def shares(value, unit):
        return value * (100 if unit == "lots_100_shares" else 1)
    diffs = []
    for day in sorted(first.keys() | second.keys()):
        if day not in first or day not in second:
            diffs.append({"date": day, "field": "date", "issue": "missing_in_primary" if day not in first else "missing_in_secondary"})
            continue
        for field in FIELDS:
            a, b = first[day][field], second[day][field]
            if any(isinstance(v, bool) or not isinstance(v, (int, float)) or not math.isfinite(v) for v in (a, b)):
                raise ValueError("non-finite numeric value")
            if field == "volume":
                a, b = shares(a, punit), shares(b, sunit)
                tol = volume_tolerance * max(abs(a), abs(b), 1)
            else:
                tol = price_tolerance
            if abs(a - b) > tol:
                diffs.append({"date": day, "field": field, "primary": a, "secondary": b})
    passed = independent and not diffs
    shared_days = sorted(first.keys() & second.keys())
    primary_only = sorted(first.keys() - second.keys())
    secondary_only = sorted(second.keys() - first.keys())
    return {
        "schema_version": "0.1", "symbol": primary["symbol"],
        "primary_upstream": primary.get("upstream"),
        "secondary_upstream": secondary.get("upstream"),
        "independent_upstream": independent,
        "independent_source_verified": False,
        "cross_source_numerical_agreement": passed,
        "status": "passed" if passed else "failed",
        "primary_record_count": len(first),
        "secondary_record_count": len(second),
        "difference_count": len(diffs),
        "date_coverage": {
            "requested_start_date": primary["start_date"],
            "requested_end_date": primary["end_date"],
            "primary_first_date": min(first),
            "primary_last_date": max(first),
            "secondary_first_date": min(second),
            "secondary_last_date": max(second),
            "shared_trading_date_count": len(shared_days),
            "primary_only_date_count": len(primary_only),
            "secondary_only_date_count": len(secondary_only),
            "primary_only_dates": primary_only,
            "secondary_only_dates": secondary_only,
            "exchange_calendar_checked": False,
        },
        "differences": diffs,
        "price_tolerance_cny": price_tolerance,
        "volume_relative_tolerance": volume_tolerance,
        "scope": "cross-source numerical agreement only; not exchange-authoritative verification",
    }


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument("--primary", required=True)
    parser.add_argument("--secondary", required=True)
    parser.add_argument("--report", required=True)
    args = parser.parse_args(argv)
    primary = json.loads(Path(args.primary).read_text(encoding="utf-8"))
    secondary = json.loads(Path(args.secondary).read_text(encoding="utf-8"))
    result = compare(primary, secondary)
    Path(args.report).write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print("Cross-check:", result["status"], "differences:", result["difference_count"])
    return 0 if result["status"] == "passed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
