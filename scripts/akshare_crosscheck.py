"""Offline cross-check of two independently sourced daily OHLCV snapshots.

The second snapshot must be acquired separately; this tool never claims independence
merely because a second file exists. No market requests or trading operations.
"""
import argparse
import json
import math
from pathlib import Path


FIELDS = ("open", "high", "low", "close", "volume")


def _rows(snapshot):
    result = {}
    for row in snapshot.get("records", []):
        day = row["date"]
        if day in result:
            raise ValueError("duplicate trading date")
        result[day] = row
    if not result:
        raise ValueError("empty snapshot")
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
    return {
        "schema_version": "0.1", "symbol": primary["symbol"],
        "primary_upstream": primary.get("upstream"),
        "secondary_upstream": secondary.get("upstream"),
        "independent_upstream": independent,
        "independent_source_verified": passed,
        "status": "passed" if passed else "failed",
        "primary_record_count": len(first),
        "secondary_record_count": len(second),
        "difference_count": len(diffs),
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
