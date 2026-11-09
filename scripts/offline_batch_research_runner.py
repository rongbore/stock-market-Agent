"""Run bounded historical research briefs from explicit local inputs only."""
import argparse
from datetime import date
import json
import math
import os
from pathlib import Path
import tempfile

from scripts.batch_research_plan import build_batch_plan, MAX_SYMBOLS
from scripts.market_research_brief import build_brief

MAX_INPUT_BYTES = 20 * 1024 * 1024
MAX_POINTS_PER_REPORT = 10000


def _validated_plan(plan):
    if not isinstance(plan, dict):
        raise ValueError("plan must be an object")
    expected = build_batch_plan(plan.get("symbols"), plan.get("analysis_date"))
    try:
        actual_json = json.dumps(plan, sort_keys=True, allow_nan=False, separators=(",", ":"))
    except (TypeError, ValueError) as exc:
        raise ValueError("invalid plan representation") from exc
    if actual_json != json.dumps(expected, sort_keys=True, separators=(",", ":")):
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
    if (not isinstance(reports_by_symbol, dict) or len(reports_by_symbol) > MAX_SYMBOLS
            or any(symbol not in plan["symbols"] for symbol in reports_by_symbol)):
        raise ValueError("reports must map only planned symbols to report objects")
    results = []
    for job in plan["jobs"]:
        result = {"job_id": job["job_id"], "symbol": job["symbol"],
                  "source_verified": False, "brief": None}
        if job["symbol"] not in reports_by_symbol:
            result.update(status="MISSING_INPUT", reason="trend_report_not_supplied")
        else:
            try:
                brief = _brief_for_job(reports_by_symbol[job["symbol"]], job)
            except (ValueError, TypeError, OverflowError):
                result.update(status="FAILED_INPUT_VALIDATION", reason="invalid_symbol_dates_or_prices")
            else:
                result.update(status="COMPLETED_UNVERIFIED", reason=None, brief=brief)
        results.append(result)
    succeeded = sum(result["status"] == "COMPLETED_UNVERIFIED" for result in results)
    return {"schema_version": "0.1", "plan_id": plan["plan_id"],
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
    return json.loads(data)


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
