"""Offline technical indicators for validated shared-date closing prices.

Descriptive historical observations only, not a prediction or trading signal.
"""
import math


def moving_average(values, window):
    if not isinstance(window, int) or isinstance(window, bool) or window < 1:
        raise ValueError("invalid moving average window")
    if not isinstance(values, list) or len(values) > 100000:
        raise ValueError("invalid price series")
    result = []
    running = 0.0
    for i, price in enumerate(values):
        if isinstance(price, bool) or not isinstance(price, (int, float)) or not math.isfinite(price) or price <= 0:
            raise ValueError("invalid close price")
        running += price
        if i >= window:
            running -= values[i - window]
        result.append(running / window if i >= window - 1 else None)
    return result


def technical_summary(report):
    """Add MA5/MA20 only when enough real shared dates are available."""
    prices = report.get("prices")
    dates = report.get("dates")
    if not isinstance(dates, list) or not isinstance(prices, list) or len(prices) != len(dates):
        raise ValueError("dates and prices must align")
    if not prices:
        return {"status": "insufficient_data", "ma5": None, "ma20": None,
                "observation": "缺少有效行情，无法判断趋势"}
    ma5 = moving_average(prices, 5)
    ma20 = moving_average(prices, 20)
    if len(prices) < 20:
        observation = "不足20个共同交易日，无法比较MA5与MA20"
        status = "insufficient_data"
    else:
        status = "descriptive_only"
        if ma5[-1] > ma20[-1]:
            observation = "MA5高于MA20（历史均线观察，不代表未来上涨）"
        elif ma5[-1] < ma20[-1]:
            observation = "MA5低于MA20（历史均线观察，不代表未来下跌）"
        else:
            observation = "MA5与MA20接近或相等，单凭均线无法判断"
    return {"status": status, "ma5": ma5, "ma20": ma20,
            "observation": observation,
            "source_verified": False, "investment_signal": False}
