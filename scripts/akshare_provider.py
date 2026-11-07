"""Optional read-only AKShare adapters. AKShare data is not independently verified."""
from datetime import date, datetime, timezone
import re

SYMBOL_RE = re.compile(r"^[0-9]{6}\.(SZ|SS)$")


def _symbol(value):
    if not isinstance(value, str) or not SYMBOL_RE.fullmatch(value):
        raise ValueError("symbol must be 6 digits followed by .SZ or .SS")
    return value[:6]


def _dates(start_date, end_date):
    if not isinstance(start_date, str) or not isinstance(end_date, str):
        raise ValueError("dates must be ISO strings")
    try:
        start, end = date.fromisoformat(start_date), date.fromisoformat(end_date)
    except ValueError as exc:
        raise ValueError("dates must use YYYY-MM-DD") from exc
    if start.isoformat() != start_date or end.isoformat() != end_date or start > end:
        raise ValueError("invalid date range")
    return start, end


def _client(client):
    if client is not None:
        return client
    try:
        import akshare
    except ImportError as exc:
        raise RuntimeError("Install optional dependency: pip install akshare") from exc
    return akshare


def _records(frame, required):
    if not hasattr(frame, "to_dict"):
        raise ValueError("AKShare returned unexpected data type")
    rows = frame.to_dict(orient="records")
    if not isinstance(rows, list) or len(rows) > 100000:
        raise ValueError("AKShare returned invalid record count")
    for row in rows:
        if not isinstance(row, dict) or not all(k in row for k in required):
            raise ValueError("AKShare response missing required columns")
    return rows


def _iso(value):
    if hasattr(value, "date") and not isinstance(value, date):
        value = value.date()
    if isinstance(value, date):
        return value.isoformat()
    if isinstance(value, str):
        try:
            parsed = date.fromisoformat(value)
        except ValueError as exc:
            raise ValueError("invalid trading date") from exc
        if parsed.isoformat() != value:
            raise ValueError("trading date must use YYYY-MM-DD")
        return parsed.isoformat()
    raise ValueError("invalid trading date")


def _number(value):
    if isinstance(value, bool):
        raise ValueError("invalid price")
    try:
        number = float(value)
    except (ValueError, TypeError) as exc:
        raise ValueError("invalid price") from exc
    import math
    if not math.isfinite(number) or number < 0:
        raise ValueError("invalid price")
    return number


def fetch_a_share_daily(symbol, start_date, end_date, *, adjust="", client=None):
    """Return daily OHLCV; no orders, brokerage access, or paid model calls."""
    code = _symbol(symbol)
    start, end = _dates(start_date, end_date)
    if adjust not in ("", "qfq", "hfq"):
        raise ValueError("adjust must be '', qfq or hfq")
    ak = _client(client)
    frame = ak.stock_zh_a_hist(symbol=code, period="daily",
                               start_date=start.strftime("%Y%m%d"),
                               end_date=end.strftime("%Y%m%d"), adjust=adjust)
    rows = _records(frame, ("日期", "开盘", "收盘", "最高", "最低", "成交量"))
    result = []
    seen = set()
    for row in rows:
        day = _iso(row["日期"])
        if not start.isoformat() <= day <= end.isoformat() or day in seen:
            raise ValueError("out-of-range or duplicate trading date")
        seen.add(day)
        item = {"date": day, "open": _number(row["开盘"]),
                "close": _number(row["收盘"]), "high": _number(row["最高"]),
                "low": _number(row["最低"]), "volume": _number(row["成交量"])}
        if item["low"] > min(item["open"], item["close"]) or item["high"] < max(item["open"], item["close"]):
            raise ValueError("inconsistent OHLC")
        result.append(item)
    result.sort(key=lambda r: r["date"])
    return {"schema_version": "0.1", "symbol": symbol, "source": "akshare",
            "upstream": "eastmoney", "interface": "stock_zh_a_hist",
            "akshare_version": str(getattr(ak, "__version__", "unknown")),
            "adjust": adjust, "volume_unit": "lots_100_shares",
            "price_unit": "CNY_per_share", "start_date": start_date, "end_date": end_date,
            "retrieved_at": datetime.now(timezone.utc).isoformat(),
            "source_content_verified": False, "historical_point_in_time_verified": False,
            "records": result}


def fetch_cninfo_disclosure_index(symbol, start_date, end_date, *, client=None):
    """Get CNINFO announcement index via AKShare; not verified evidence."""
    code = _symbol(symbol)
    start, end = _dates(start_date, end_date)
    ak = _client(client)
    frame = ak.stock_zh_a_disclosure_report_cninfo(
        symbol=code, market="沪深京", keyword="", category="",
        start_date=start.strftime("%Y%m%d"), end_date=end.strftime("%Y%m%d"))
    rows = _records(frame, ("代码", "公告标题", "公告时间"))
    if not rows:
        raise ValueError("AKShare returned no disclosures; verify upstream availability")
    for row in rows:
        if str(row["代码"]).strip() != code:
            raise ValueError("AKShare disclosure symbol mismatch")
        if not str(row["公告标题"]).strip():
            raise ValueError("AKShare disclosure title missing")
        day = _iso(row["公告时间"])
        if not start.isoformat() <= day <= end.isoformat():
            raise ValueError("AKShare disclosure date outside requested range")
    return {"schema_version": "0.1", "symbol": symbol, "source": "akshare",
            "upstream": "cninfo", "interface": "stock_zh_a_disclosure_report_cninfo",
            "akshare_version": str(getattr(ak, "__version__", "unknown")),
            "start_date": start_date, "end_date": end_date,
            "retrieved_at": datetime.now(timezone.utc).isoformat(),
            "source_content_verified": False, "historical_point_in_time_verified": False,
            "raw_columns": list(frame.columns), "records": [
                {str(k): str(v) for k, v in row.items()} for row in rows]}
