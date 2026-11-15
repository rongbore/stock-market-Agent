"""Compare supplied session dates with a snapshot without certifying the calendar."""
import hashlib

from scripts.akshare_provider import _dates, _symbol
from scripts.offline_batch_research_runner import _canonical_json_bytes


def validate_calendar(calendar, symbol, start_date, end_date):
    """Require a bounded, explicit exchange/window declaration before collection."""
    _symbol(symbol)
    start, end = _dates(start_date, end_date)
    if type(calendar) is not dict or set(calendar) != {
            "schema_version", "exchange", "start_date", "end_date", "source", "sessions"}:
        raise ValueError("calendar requires exact fields")
    if (calendar["schema_version"] != "0.1" or calendar["exchange"] != symbol[-2:]
            or calendar["start_date"] != start_date or calendar["end_date"] != end_date):
        raise ValueError("calendar exchange/window mismatch")
    if type(calendar["source"]) is not str or not calendar["source"].strip() or len(calendar["source"]) > 500:
        raise ValueError("calendar source label required")
    sessions = calendar["sessions"]
    if type(sessions) is not list or len(sessions) > 367:
        raise ValueError("calendar sessions must be a bounded list")
    for session in sessions:
        day, _ = _dates(session, session)
        if not start <= day <= end:
            raise ValueError("calendar session outside declared window")
    if sessions != sorted(set(sessions)):
        raise ValueError("calendar sessions must be sorted and unique")
    _canonical_json_bytes(calendar)
    return calendar


def check_calendar_coverage(calendar, snapshot):
    """Missing sessions may indicate suspensions; disagreement needs review."""
    validate_calendar(calendar, snapshot["symbol"], snapshot["start_date"], snapshot["end_date"])
    dates = [row["date"] for row in snapshot["records"]]
    for day in dates:
        _dates(day, day)
    if len(set(dates)) != len(dates):
        raise ValueError("duplicate snapshot dates")
    expected, observed = set(calendar["sessions"]), set(dates)
    missing, unexpected = sorted(expected - observed), sorted(observed - expected)
    return {"status": "MATCH" if not missing and not unexpected else "REVIEW_REQUIRED",
            "calendar_coverage_checked": True, "exchange_calendar_verified": False,
            "calendar_sha256": hashlib.sha256(_canonical_json_bytes(calendar)).hexdigest(),
            "expected_count": len(expected), "observed_count": len(observed),
            "missing_dates": missing, "unexpected_dates": unexpected}
