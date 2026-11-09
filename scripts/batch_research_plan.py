"""Create a bounded offline research plan; never execute or schedule its jobs."""
import argparse
from datetime import date
import hashlib
import json
import os
from pathlib import Path
import tempfile

from scripts.akshare_provider import _symbol

MAX_SYMBOLS = 100


def build_batch_plan(symbols, analysis_date):
    """Plan one existing offline brief per explicit A-share symbol and date."""
    if not isinstance(symbols, list) or not 1 <= len(symbols) <= MAX_SYMBOLS:
        raise ValueError("symbols must be a list of 1 to 100 explicit A-share symbols")
    for symbol in symbols:
        _symbol(symbol)
    if len(set(symbols)) != len(symbols):
        raise ValueError("duplicate symbols are not allowed")
    if not isinstance(analysis_date, str):
        raise ValueError("analysis_date must use YYYY-MM-DD")
    try:
        parsed = date.fromisoformat(analysis_date)
    except ValueError as exc:
        raise ValueError("analysis_date must use YYYY-MM-DD") from exc
    if parsed.isoformat() != analysis_date:
        raise ValueError("analysis_date must use YYYY-MM-DD")
    symbols = sorted(symbols)
    contract = {"schema_version": "0.1", "symbols": symbols, "analysis_date": analysis_date,
                "operation": "offline_market_research_brief"}
    digest = hashlib.sha256(json.dumps(contract, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
    jobs = []
    for symbol in symbols:
        job_id = f"research-{parsed.strftime('%Y%m%d')}-{symbol.lower().replace('.', '-')}"
        jobs.append({
            "job_id": job_id, "symbol": symbol, "analysis_date": analysis_date,
            "operation": contract["operation"], "status": "PENDING_INPUTS",
            "required_inputs": ["per_symbol_trend_report_json"],
            "output_relative_path": f"{job_id}/research_brief_unverified.json",
            "source_verified": False, "is_prediction": False, "is_trading_advice": False,
        })
    return {**contract, "plan_id": f"batch-{digest}", "status": "PLANNED_ONLY",
            "job_count": len(jobs), "jobs": jobs,
            "jobs_executed": 0, "execution_authorized": False,
            "limitations": [
                "No input data has been loaded or validated.",
                "The analysis date is a requested cutoff, not proof of point-in-time availability.",
                "This plan does not screen stocks, run jobs, create a schedule, or call models.",
            ]}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--symbols", required=True, nargs="+", help="Explicit .SZ/.SS symbols; at most 100")
    parser.add_argument("--analysis-date", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args(argv)
    result = build_batch_plan(args.symbols, args.analysis_date)
    output = Path(args.output)
    if output.is_symlink():
        raise ValueError("output must not be a symbolic link")
    output.parent.mkdir(parents=True, exist_ok=True)
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", dir=output.parent,
                                         delete=False) as stream:
            temporary = Path(stream.name)
            json.dump(result, stream, ensure_ascii=False, indent=2)
            stream.write("\n")
        os.replace(temporary, output)
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
