"""Optional Sina-backed A-share daily history via AKShare (read-only).

Uses stock_zh_a_daily; availability, adjustment semantics and units are
checked at runtime. The resulting snapshot is not exchange-authenticated.
"""
from datetime import datetime, timezone

from scripts.akshare_provider import _client, _dates, _iso, _number, _records, _symbol


def fetch_sina_daily(symbol, start_date, end_date, *, adjust="", client=None):
    code = _symbol(symbol)
    start, end = _dates(start_date, end_date)
    if adjust not in ("", "qfq", "hfq"):
        raise ValueError("unsupported adjustment")
    prefix = "sz" if symbol.endswith(".SZ") else "sh"
    ak = _client(client)
    frame = ak.stock_zh_a_daily(
        symbol=prefix + code,
        start_date=start.strftime("%Y%m%d"),
        end_date=end.strftime("%Y%m%d"),
        adjust=adjust,
    )
    rows = _records(frame, ("date", "open", "high", "low", "close", "volume"))
    seen = set()
    records = []
    for row in rows:
        day = _iso(row["date"])
        if not start.isoformat() <= day <= end.isoformat() or day in seen:
            raise ValueError("out-of-range or duplicate trading date")
        seen.add(day)
        item = {"date": day, "open": _number(row["open"]),
                "high": _number(row["high"]), "low": _number(row["low"]),
                "close": _number(row["close"]), "volume": _number(row["volume"])}
        if item["low"] > min(item["open"], item["close"]) or item["high"] < max(item["open"], item["close"]):
            raise ValueError("inconsistent OHLC")
        records.append(item)
    records.sort(key=lambda item: item["date"])
    return {
        "schema_version": "0.1", "symbol": symbol,
        "source": "akshare", "upstream": "sina",
        "interface": "stock_zh_a_daily",
        "akshare_version": str(getattr(ak, "__version__", "unknown")),
        "adjust": adjust, "price_unit": "CNY_per_share",
        "volume_unit": "shares",
        "start_date": start_date, "end_date": end_date,
        "retrieved_at": datetime.now(timezone.utc).isoformat(),
        "source_content_verified": False,
        "historical_point_in_time_verified": False,
        "records": records,
    }
