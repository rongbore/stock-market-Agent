"""Offline daily-bar contract for future backtests; not a simulation or PIT proof."""
from datetime import date, datetime, time, timedelta, timezone
import math

from scripts.akshare_provider import _symbol

ADJUSTMENTS = {"unadjusted": "", "forward_adjusted": "qfq", "backward_adjusted": "hfq"}
UPSTREAMS = {"eastmoney": ("stock_zh_a_hist", "lots_100_shares", 100),
             "sina": ("stock_zh_a_daily", "shares", 1)}
SHANGHAI = timezone(timedelta(hours=8))
ROW_KEYS = {"date", "open", "high", "low", "close", "volume"}


def _day(value):
    if not isinstance(value, str):
        raise ValueError("date must use YYYY-MM-DD")
    try:
        parsed = date.fromisoformat(value)
    except ValueError as exc:
        raise ValueError("date must use YYYY-MM-DD") from exc
    if parsed.isoformat() != value:
        raise ValueError("date must use YYYY-MM-DD")
    return parsed


def _instant(value):
    if not isinstance(value, str):
        raise ValueError("timestamp must include timezone")
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ValueError("invalid timestamp") from exc
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise ValueError("timestamp must include timezone")
    return parsed


def build_backtest_dataset(snapshot, *, evidence_as_of, expected_adjustment):
    """Validate known AKShare snapshots and normalize volume to shares.

    evidence_as_of bounds local evidence retrieval and daily-bar closure. It is
    not a simulated decision time and does not establish historical availability.
    """
    if not isinstance(snapshot, dict):
        raise ValueError("snapshot must be an object")
    if not isinstance(expected_adjustment, str) or expected_adjustment not in ADJUSTMENTS:
        raise ValueError("explicit supported adjustment required")
    if snapshot.get("adjust") != ADJUSTMENTS[expected_adjustment]:
        raise ValueError("adjustment mismatch")
    if snapshot.get("schema_version") != "0.1" or snapshot.get("source") != "akshare":
        raise ValueError("unsupported snapshot schema or source")
    upstream = snapshot.get("upstream")
    if not isinstance(upstream, str) or upstream not in UPSTREAMS:
        raise ValueError("unsupported upstream")
    interface, volume_unit, multiplier = UPSTREAMS[upstream]
    if (snapshot.get("interface") != interface or snapshot.get("volume_unit") != volume_unit
            or snapshot.get("price_unit") != "CNY_per_share"):
        raise ValueError("source interface or units mismatch")
    symbol = snapshot.get("symbol")
    _symbol(symbol)
    if any(snapshot.get(flag) is not False for flag in
           ("source_content_verified", "historical_point_in_time_verified")):
        raise ValueError("verification flags must remain explicitly false")
    cutoff = _instant(evidence_as_of)
    retrieved = _instant(snapshot.get("retrieved_at"))
    if retrieved > cutoff:
        raise ValueError("snapshot retrieved after evidence cutoff")
    start, end = _day(snapshot.get("start_date")), _day(snapshot.get("end_date"))
    if start > end:
        raise ValueError("reversed requested date range")
    rows = snapshot.get("records")
    if not isinstance(rows, list) or not 1 <= len(rows) <= 100000:
        raise ValueError("records must contain 1 to 100000 daily bars")
    bars = []
    previous = None
    for row in rows:
        if not isinstance(row, dict) or set(row) != ROW_KEYS:
            raise ValueError("unexpected daily bar fields")
        day = _day(row["date"])
        if (previous is not None and day <= previous) or not start <= day <= end:
            raise ValueError("bars must be unique, ascending and within requested dates")
        if day.weekday() >= 5:
            raise ValueError("weekend daily bar")
        # A declared date alone must not admit an unfinished same-day bar.
        close = datetime.combine(day, time(15), SHANGHAI)
        if close > cutoff or close > retrieved:
            raise ValueError("daily bar closes after retrieval or evidence cutoff")
        values = [row[key] for key in ("open", "high", "low", "close", "volume")]
        if any(type(value) not in (int, float) for value in values):
            raise ValueError("OHLCV must be finite numbers")
        try:
            finite = all(math.isfinite(value) for value in values)
        except OverflowError:
            finite = False
        if not finite:
            raise ValueError("OHLCV must be finite numbers")
        op, high, low, last, volume = values
        if min(op, high, low, last) <= 0 or volume < 0 or not low <= min(op, last) <= max(op, last) <= high:
            raise ValueError("inconsistent OHLCV")
        normalized_volume = volume * multiplier
        try:
            valid_volume = math.isfinite(normalized_volume)
        except OverflowError:
            valid_volume = False
        if not valid_volume:
            raise ValueError("normalized volume outside finite range")
        bars.append({**row, "volume": normalized_volume})
        previous = day
    return {
        "schema_version": "0.1", "symbol": symbol, "frequency": "daily",
        "adjustment": expected_adjustment, "price_unit": "CNY_per_share", "volume_unit": "shares",
        "evidence_as_of": cutoff.isoformat(), "bars": bars,
        "provenance": {"source": "akshare", "upstream": upstream, "interface": interface,
                       "retrieved_at": retrieved.isoformat(), "input_volume_unit": volume_unit,
                       "requested_start": start.isoformat(), "requested_end": end.isoformat()},
        "source_content_verified": False, "historical_point_in_time_verified": False,
        "exchange_calendar_checked": False,
        "status": "STRUCTURE_VALIDATED_UNVERIFIED",
        "limitations": ["Not proof of historical availability or exchange authenticity.",
                        "No exchange holiday, suspension or missing-session completeness check.",
                        "Adjusted series may incorporate corporate actions learned after simulated dates.",
                        "No strategy, fills, costs, returns or trading actions are computed."],
    }
