"""Offline financial metric citations linked to an unverified disclosure ledger.

This module validates references, not financial statements or source authenticity.
"""
import argparse
import json
import math
from pathlib import Path


METRICS = {"revenue", "net_profit", "total_assets", "operating_cash_flow"}
UNITS = {"CNY", "CNY_million", "CNY_billion"}


def link_metrics(ledger, metrics):
    if not isinstance(ledger, dict) or not isinstance(ledger.get("records"), list):
        raise ValueError("invalid evidence ledger")
    symbol = ledger.get("symbol")
    if not isinstance(symbol, str) or not symbol:
        raise ValueError("invalid ledger symbol")
    if not isinstance(metrics, list) or len(metrics) > 500:
        raise ValueError("invalid metrics collection")
    index = {}
    for record in ledger["records"]:
        if not isinstance(record, dict) or record.get("symbol") != symbol:
            raise ValueError("invalid ledger record")
        key = (record.get("kind"), record.get("published_date"), record.get("source_url"))
        if any(not isinstance(x, str) or not x for x in key) or key in index:
            raise ValueError("invalid or duplicate ledger reference")
        index[key] = record
    result, seen = [], set()
    for row in metrics:
        if not isinstance(row, dict):
            raise ValueError("invalid metric record")
        name, unit, period = row.get("metric"), row.get("unit"), row.get("period")
        if name not in METRICS or unit not in UNITS:
            raise ValueError("unsupported metric or unit")
        if not isinstance(period, str) or not period or len(period) > 40:
            raise ValueError("invalid period")
        value = row.get("value")
        if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
            raise ValueError("invalid financial value")
        ref = row.get("source_ref")
        if not isinstance(ref, dict):
            raise ValueError("source reference required")
        key = (ref.get("kind"), ref.get("published_date"), ref.get("source_url"))
        if key not in index:
            raise ValueError("source reference not in ledger")
        if row.get("symbol") != symbol:
            raise ValueError("metric symbol mismatch")
        unique = (name, period, unit, key)
        if unique in seen:
            raise ValueError("duplicate financial metric")
        seen.add(unique)
        result.append({
            "symbol": symbol, "metric": name, "period": period,
            "value": value, "unit": unit,
            "source_ref": {"kind": key[0], "published_date": key[1], "source_url": key[2]},
            "source_content_verified": False, "metric_value_verified": False,
            "historical_point_in_time_verified": False,
        })
    return {"schema_version": "0.1", "symbol": symbol,
            "metrics": result, "metric_count": len(result),
            "all_metrics_verified": False,
            "note": "引用关系只证明记录关联，不代表财报内容、指标数值或披露时点已核验。"}


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument("--ledger", required=True)
    parser.add_argument("--metrics", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args(argv)
    ledger = json.loads(Path(args.ledger).read_text(encoding="utf-8"))
    metrics = json.loads(Path(args.metrics).read_text(encoding="utf-8"))
    result = link_metrics(ledger, metrics)
    Path(args.output).write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
