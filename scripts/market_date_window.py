"""Resolve completed calendar-day windows for public daily-market collection."""
from datetime import datetime, timedelta, timezone
import os

from scripts.backtest_data_contract import _day

SHANGHAI = timezone(timedelta(hours=8))


def resolve_market_window(start_date=None, end_date=None, *, now=None):
    """Default to 21 calendar days ending at Shanghai yesterday, not a trading calendar."""
    current = now if now is not None else datetime.now(timezone.utc)
    if not isinstance(current, datetime) or current.tzinfo is None or current.utcoffset() is None:
        raise ValueError("now must be timezone aware")
    last_completed = current.astimezone(SHANGHAI).date() - timedelta(days=1)
    missing_start, missing_end = start_date in (None, ""), end_date in (None, "")
    if missing_start != missing_end:
        raise ValueError("start_date and end_date must both be supplied or both omitted")
    if missing_start:
        end = last_completed
        start = end - timedelta(days=20)
        mode = "rolling_calendar_days"
    else:
        start, end = _day(start_date), _day(end_date)
        mode = "explicit_history"
    if start > end or end > last_completed or (end - start).days > 366:
        raise ValueError("invalid date window: ordered, at most 366-day span, ending before Shanghai today required")
    return {"start_date": start.isoformat(), "end_date": end.isoformat(), "mode": mode,
            "timezone": "Asia/Shanghai", "exchange_calendar_checked": False}


def main():
    window = resolve_market_window(os.environ.get("REQUEST_START_DATE"), os.environ.get("REQUEST_END_DATE"))
    # Only validated ISO dates reach GITHUB_ENV; no raw dispatch input is echoed.
    print("STOCK_START_DATE=" + window["start_date"])
    print("STOCK_END_DATE=" + window["end_date"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
