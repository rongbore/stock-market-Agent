"""Offline quality checks for user-supplied, unverified financial metric records.

This validates internal consistency only; it does not verify filing content.
"""
import argparse
import json
import math
import re
from pathlib import Path

_ALLOWED = {"revenue", "net_profit", "total_assets", "operating_cash_flow"}
_SCALE = {"CNY": 1, "CNY_million": 1_000_000, "CNY_billion": 1_000_000_000}
_PERIOD = re.compile(r"^(20[0-9]{2})(Q[1-4]|FY|H[12])$")


def assess_quality(payload):
    if not isinstance(payload, dict) or not isinstance(payload.get("metrics"), list):
        raise ValueError("invalid metric payload")
    symbol = payload.get("symbol")
    if not isinstance(symbol, str) or not symbol.strip():
        raise ValueError("invalid symbol")
    records = payload["metrics"]
    if len(records) > 500:
        raise ValueError("too many metric records")
    seen = set()
    issues = []
    normalized = {}
    for i, row in enumerate(records):
        if not isinstance(row, dict) or row.get("symbol") != symbol:
            raise ValueError("invalid metric symbol")
        name, period, unit = row.get("metric"), row.get("period"), row.get("unit")
        if not isinstance(name, str) or name not in _ALLOWED or not isinstance(period, str) or not _PERIOD.fullmatch(period):
            raise ValueError("invalid metric name or period")
        if not isinstance(unit, str) or unit not in _SCALE:
            raise ValueError("invalid financial unit")
        value = row.get("value")
        if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
            raise ValueError("invalid financial value")
        ref = row.get("source_ref")
        if not isinstance(ref, dict) or any(not isinstance(ref.get(k), str) or not ref[k] for k in ("kind", "published_date", "source_url")):
            raise ValueError("missing source reference")
        key = (name, period)
        if key in seen:
            issues.append({"code": "duplicate_metric_period", "index": i, "metric": name, "period": period})
        seen.add(key)
        if name in ("revenue", "total_assets") and value < 0:
            issues.append({"code": "negative_nonnegative_metric", "index": i, "metric": name, "period": period})
        if row.get("metric_value_verified") is True or row.get("source_content_verified") is True:
            issues.append({"code": "unsupported_verification_claim", "index": i, "metric": name, "period": period})
        scaled = value * _SCALE[unit]
        if not math.isfinite(scaled):
            raise ValueError("normalized financial value is not finite")
        normalized[f"{name}:{period}"] = scaled
    return {
        "schema_version": "0.1", "symbol": symbol, "metric_count": len(records),
        "status": "needs_review" if issues else "structurally_consistent_unverified",
        "issues": issues, "normalized_values_cny": normalized,
        "source_content_verified": False, "financial_values_verified": False,
        "note": "只检查内部结构和数值关系；无法证明财报来源或指标真实。",
    }


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args(argv)
    payload = json.loads(Path(args.input).read_text(encoding="utf-8"))
    result = assess_quality(payload)
    Path(args.output).write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return 0 if not result["issues"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
