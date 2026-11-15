"""Opt-in public-market collection to one unverified offline research artifact."""
import argparse
import json
from datetime import datetime, timezone
import os
from pathlib import Path
import tempfile

from scripts.akshare_provider import _dates, _symbol, fetch_a_share_daily
from scripts.akshare_sina_provider import fetch_sina_daily
from scripts.offline_batch_pipeline import build_pipeline
from scripts.offline_batch_research_runner import _canonical_json_bytes
from scripts.offline_research_dashboard import build_dashboard
from scripts.snapshot_research_config import build_snapshot_research_config
from scripts.market_calendar_coverage import check_calendar_coverage, validate_calendar
from scripts.batch_research_summary import _unique_object


def collect_market_research(symbol, start_date, end_date, upstream, *, fetcher=None, calendar=None):
    """Collect one explicitly selected source; sanitize failures without raw errors."""
    _symbol(symbol)
    start, end = _dates(start_date, end_date)
    if (end - start).days > 366 or upstream not in ("eastmoney", "sina"):
        raise ValueError("select eastmoney/sina and a window of at most 366 days")
    if calendar is not None:
        validate_calendar(calendar, symbol, start_date, end_date)
    request = {"symbol": symbol, "start_date": start_date, "end_date": end_date,
               "upstream": upstream, "adjustment": "unadjusted"}
    result = {"schema_version": "0.1", "request": request,
              "source_verified": False, "historical_point_in_time_verified": False,
              "status": "FAILED", "stage": "collection", "reason": "collection_failed"}
    fetcher = fetcher or (fetch_a_share_daily if upstream == "eastmoney" else fetch_sina_daily)
    try:
        snapshot = fetcher(symbol, start_date, end_date, adjust="")
    except Exception:
        return result
    result.update(stage="validation", reason="snapshot_or_research_validation_failed")
    try:
        if (type(snapshot) is not dict or snapshot.get("symbol") != symbol
                or snapshot.get("upstream") != upstream or snapshot.get("start_date") != start_date
                or snapshot.get("end_date") != end_date):
            raise ValueError("provider identity mismatch")
        coverage = check_calendar_coverage(calendar, snapshot) if calendar is not None else None
        if coverage is not None and coverage["status"] != "MATCH":
            result.update(stage="calendar_coverage", reason="calendar_date_mismatch", calendar_coverage=coverage)
            return result
        config = build_snapshot_research_config({
            "schema_version": "0.1", "data_kind": "UNVERIFIED_LOCAL", "analysis_date": end_date,
            "evidence_as_of": datetime.now(timezone.utc).isoformat(), "expected_adjustment": "unadjusted",
            "snapshots": {symbol: snapshot}})
        research = build_pipeline(config)
        dashboard = build_dashboard(batch_config=config)
        artifact = {"schema_version": "0.1", "request": request,
                    "status": "COLLECTED_RESEARCH_UNVERIFIED", "stage": "complete", "reason": None,
                    "snapshot": snapshot, "batch_config": config, "research": research,
                    "dashboard_html": dashboard, "source_verified": False,
                    "historical_point_in_time_verified": False}
        if coverage is not None:
            artifact["calendar_coverage"] = coverage
        _canonical_json_bytes(artifact)
        return artifact
    except Exception:
        return result


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--symbol", required=True)
    parser.add_argument("--start-date", required=True)
    parser.add_argument("--end-date", required=True)
    parser.add_argument("--upstream", required=True, choices=("eastmoney", "sina"))
    parser.add_argument("--allow-network", required=True, action="store_true")
    parser.add_argument("--output", required=True)
    parser.add_argument("--calendar", help="explicit local calendar JSON; mismatch blocks research")
    args = parser.parse_args(argv)
    calendar = None
    if args.calendar:
        with Path(args.calendar).open("rb") as stream:
            raw = stream.read(65537)
        if len(raw) > 65536:
            raise ValueError("calendar input too large")
        calendar = json.loads(raw, object_pairs_hook=_unique_object)
        validate_calendar(calendar, args.symbol, args.start_date, args.end_date)
    output = Path(args.output)
    if output.exists() or output.is_symlink():
        raise FileExistsError("collection output must be a new file")
    # Preflight the destination before any opt-in network request. Creating a
    # temporary file tests actual write access rather than permission bits alone.
    output.parent.mkdir(parents=True, exist_ok=True)
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(mode="wb", dir=output.parent, delete=False) as stream:
            temporary = Path(stream.name)
        artifact = collect_market_research(args.symbol, args.start_date, args.end_date, args.upstream, calendar=calendar)
        encoded = _canonical_json_bytes(artifact) + b"\n"
        with temporary.open("wb") as stream:
            stream.write(encoded)
        # Exclusive creation preserves existing evidence, including a concurrent writer.
        os.link(temporary, output)
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)
    return 0 if artifact["status"] == "COLLECTED_RESEARCH_UNVERIFIED" else 2


if __name__ == "__main__":
    raise SystemExit(main())
