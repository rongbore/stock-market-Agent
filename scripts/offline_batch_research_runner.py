"""Run bounded historical research briefs from explicit local inputs only."""
import argparse
from datetime import date
import hashlib
import json
import math
import os
from pathlib import Path
import tempfile

from scripts.batch_research_plan import build_batch_plan, MAX_SYMBOLS
from scripts.market_research_brief import build_brief

MAX_INPUT_BYTES = 20 * 1024 * 1024
MAX_POINTS_PER_REPORT = 10000
MAX_JSON_DEPTH = 32
MAX_JSON_NODES = 100000


def _canonical_json_bytes(value):
    """Bound exact JSON types before deterministic encoding (not RFC 8785)."""
    stack = [(value, 0)]
    nodes = 0
    encoded_bound = 0
    while stack:
        item, depth = stack.pop()
        nodes += 1
        if nodes > MAX_JSON_NODES or depth > MAX_JSON_DEPTH:
            raise ValueError("JSON structure exceeds limits")
        kind = type(item)
        if item is None or kind is bool:
            encoded_bound += 5
        elif kind is int:
            if item.bit_length() > 1024:
                raise ValueError("JSON integer exceeds limits")
            encoded_bound += 312
        elif kind is float:
            if not math.isfinite(item):
                raise ValueError("JSON numbers must be finite")
            encoded_bound += 32
        elif kind is str:
            encoded_bound += len(item) * 6 + 2
        elif kind in (list, dict):
            if len(item) > MAX_JSON_NODES or nodes + len(stack) + len(item) > MAX_JSON_NODES:
                raise ValueError("JSON structure exceeds limits")
            encoded_bound += len(item) * 2 + 2
            if kind is dict:
                if any(type(key) is not str for key in item):
                    raise ValueError("JSON object keys must be strings")
                stack.extend((key, depth + 1) for key in item)
                stack.extend((entry, depth + 1) for entry in item.values())
            else:
                stack.extend((entry, depth + 1) for entry in item)
        else:
            raise ValueError("unsupported JSON value")
        if encoded_bound > MAX_INPUT_BYTES:
            raise ValueError("canonical JSON exceeds limits")
    encoded = json.dumps(value, sort_keys=True, ensure_ascii=True, allow_nan=False,
                         separators=(",", ":")).encode("ascii")
    if len(encoded) > MAX_INPUT_BYTES:
        raise ValueError("canonical JSON exceeds limits")
    return encoded


def _validated_plan(plan):
    actual_json = _canonical_json_bytes(plan)
    if not isinstance(plan, dict):
        raise ValueError("plan must be an object")
    expected = build_batch_plan(plan.get("symbols"), plan.get("analysis_date"))
    if actual_json != _canonical_json_bytes(expected):
        raise ValueError("plan does not match deterministic planning contract")
    return expected


def _brief_for_job(report, job):
    if not isinstance(report, dict) or report.get("symbol") != job["symbol"]:
        raise ValueError("report_symbol_mismatch")
    dates = report.get("dates")
    if not isinstance(dates, list) or not 1 <= len(dates) <= MAX_POINTS_PER_REPORT:
        raise ValueError("invalid_report_dates")
    cutoff = date.fromisoformat(job["analysis_date"])
    for value in dates:
        if not isinstance(value, str):
            raise ValueError("invalid_report_date")
        try:
            parsed = date.fromisoformat(value)
        except ValueError as exc:
            raise ValueError("invalid_report_date") from exc
        if parsed.isoformat() != value or parsed > cutoff:
            raise ValueError("noncanonical_or_future_report_date")
    # Existing brief checks alignment, unique ascending dates and finite positive prices.
    brief = build_brief(report)
    prices = report["prices"]
    if len(prices) > 1 and not math.isfinite((prices[-1] / prices[0] - 1) * 100):
        raise ValueError("nonfinite_price_change")
    return brief


def run_batch_plan(plan, reports_by_symbol):
    """Revalidate the entire plan, isolate bad inputs and return one in-memory bundle."""
    plan = _validated_plan(plan)
    if (type(reports_by_symbol) is not dict or len(reports_by_symbol) > MAX_SYMBOLS
            or any(type(symbol) is not str or symbol not in plan["symbols"] for symbol in reports_by_symbol)):
        raise ValueError("reports must map only planned symbols to report objects")
    results = []
    for job in plan["jobs"]:
        result = {"job_id": job["job_id"], "symbol": job["symbol"],
                  "source_verified": False, "brief": None, "input_sha256": None,
                  "input_hash_status": "missing"}
        if job["symbol"] not in reports_by_symbol:
            result.update(status="MISSING_INPUT", reason="trend_report_not_supplied")
        else:
            try:
                encoded = _canonical_json_bytes(reports_by_symbol[job["symbol"]])
            except ValueError:
                result.update(status="FAILED_INPUT_VALIDATION", reason="invalid_or_unbounded_json_input",
                              input_hash_status="rejected_noncanonical_json")
            else:
                result.update(input_sha256=hashlib.sha256(encoded).hexdigest(),
                              input_hash_status="canonical_json_sha256")
                try:
                    brief = _brief_for_job(reports_by_symbol[job["symbol"]], job)
                except (ValueError, TypeError, OverflowError):
                    result.update(status="FAILED_INPUT_VALIDATION", reason="invalid_symbol_dates_or_prices")
                else:
                    result.update(status="COMPLETED_UNVERIFIED", reason=None, brief=brief)
        results.append(result)
    succeeded = sum(result["status"] == "COMPLETED_UNVERIFIED" for result in results)
    return {"schema_version": "0.1", "plan_id": plan["plan_id"],
            "plan_sha256": hashlib.sha256(_canonical_json_bytes(plan)).hexdigest(),
            "hash_encoding": "json_sorted_keys_ascii_compact_v1",
            "analysis_date": plan["analysis_date"], "job_count": len(results),
            "succeeded_count": succeeded, "failed_count": len(results) - succeeded,
            "status": "COMPLETED_UNVERIFIED" if succeeded == len(results) else "COMPLETED_WITH_FAILURES",
            "results": results, "source_verified": False,
            "historical_point_in_time_verified": False,
            "is_prediction": False, "is_trading_advice": False}


def _load_json(path):
    with Path(path).open("rb") as stream:
        data = stream.read(MAX_INPUT_BYTES + 1)
    if len(data) > MAX_INPUT_BYTES:
        raise ValueError("input JSON too large")
    try:
        return json.loads(data)
    except (ValueError, RecursionError, UnicodeError) as exc:
        raise ValueError("invalid JSON input") from exc


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--plan", required=True)
    parser.add_argument("--reports", required=True, help="JSON object mapping symbols to inline trend reports")
    parser.add_argument("--output", required=True)
    args = parser.parse_args(argv)
    output = Path(args.output)
    if output.is_symlink() or output.resolve() in (Path(args.plan).resolve(), Path(args.reports).resolve()):
        raise ValueError("output cannot overwrite an input or target a symbolic link")
    result = run_batch_plan(_load_json(args.plan), _load_json(args.reports))
    output.parent.mkdir(parents=True, exist_ok=True)
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", dir=output.parent,
                                         delete=False) as stream:
            temporary = Path(stream.name)
            json.dump(result, stream, ensure_ascii=False, indent=2, allow_nan=False)
            stream.write("\n")
        os.replace(temporary, output)
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
