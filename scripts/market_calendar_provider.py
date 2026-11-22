"""Read one explicit Sina session list through optional AKShare; never certify it."""
from datetime import datetime, timezone
import hashlib

from scripts.akshare_provider import _client, _dates, _iso, _records
from scripts.market_date_window import resolve_market_window
from scripts.offline_batch_research_runner import _canonical_json_bytes

MAX_CALENDAR_DATES = 20000
INTERFACES = ("calendar_trade_date_hist_sina", "tool_trade_date_hist_sina")
SOURCE_URL = "https://finance.sina.com.cn/realstock/company/klc_td_sh.txt"


def fetch_sina_calendar(start_date, end_date, *, client=None, now=None):
    """Return window sessions and provenance, refusing stale or ambiguous lists.

    The supplied provider list must bracket both requested calendar dates, even
    if a boundary is a holiday. This conservative coverage check does not prove
    that sessions within the bracket are complete or exchange-authenticated.
    """
    _dates(start_date, end_date)
    resolve_market_window(start_date, end_date, now=now)
    ak = _client(client)
    selected = None
    for name in INTERFACES:
        try:
            function = getattr(ak, name)
        except AttributeError:
            continue
        if not callable(function):
            raise RuntimeError("AKShare calendar interface is not callable")
        selected = (name, function)
        break
    if selected is None:
        raise RuntimeError("supported AKShare calendar interface unavailable")
    interface, fetch = selected
    rows = _records(fetch(), ("trade_date",))
    if not 1 <= len(rows) <= MAX_CALENDAR_DATES:
        raise ValueError("calendar must contain 1 to 20000 dates")
    dates = []
    for row in rows:
        day = _iso(row["trade_date"])
        _dates(day, day)
        dates.append(day)
    if dates != sorted(set(dates)):
        raise ValueError("provider calendar dates must be ascending and unique")
    if dates[0] > start_date or dates[-1] < end_date:
        raise ValueError("provider calendar does not cover the requested range")
    sessions = [day for day in dates if start_date <= day <= end_date]
    retrieved = now if now is not None else datetime.now(timezone.utc)
    metadata = {
        "schema_version": "0.1", "source": "akshare", "upstream": "sina",
        "interface": interface, "akshare_version": str(getattr(ak, "__version__", "unknown")),
        "source_url": SOURCE_URL, "retrieved_at": retrieved.isoformat(),
        "requested_start": start_date, "requested_end": end_date,
        "observed_start": dates[0], "observed_end": dates[-1],
        "full_date_list_sha256": hashlib.sha256(_canonical_json_bytes(dates)).hexdigest(),
        "full_date_count": len(dates), "window_session_count": len(sessions),
        "source_content_verified": False, "historical_point_in_time_verified": False,
        "exchange_calendar_verified": False, "independent_source_verified": False,
        "limitations": [
            "A provider date list is not an official or independently verified exchange calendar.",
            "The observed first/last dates only bracket the window; missing interior sessions remain possible.",
            "Reusing this single list for SS/SZ is a caller assumption, not verified exchange alignment.",
            "Provider timeout behavior is inherited; no unsupported timeout parameter is passed.",
        ],
    }
    _canonical_json_bytes(metadata)
    return sessions, metadata
