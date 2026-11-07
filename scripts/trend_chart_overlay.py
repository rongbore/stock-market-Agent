"""Render MA5/MA20 overlays on an existing validated price-trend report.

Only descriptive observations; no brokerage or model API access.
"""
from html import escape
from scripts.trend_indicators import technical_summary


def overlay_svg(report):
    prices = report["prices"]
    indicators = technical_summary(report)
    if not prices:
        raise ValueError("no prices to plot")
    width, height, pad = 900, 360, 54
    valid = list(prices)
    for key in ("ma5", "ma20"):
        valid.extend(v for v in indicators[key] if v is not None)
    low, high = min(valid), max(valid)
    span = high - low or max(abs(high) * .02, 1)
    def xy(i, value):
        x = pad + (width - 2 * pad) * i / max(1, len(prices) - 1)
        y = height - pad - (value - low) / span * (height - 2 * pad)
        return f"{x:.1f},{y:.1f}"
    paths = []
    for name, series, color in (
        ("Close", prices, "#2563eb"),
        ("MA5", indicators["ma5"], "#ea580c"),
        ("MA20", indicators["ma20"], "#16a34a"),
    ):
        points = " ".join(xy(i, v) for i, v in enumerate(series) if v is not None)
        if points:
            paths.append(f'<polyline data-series="{name}" fill="none" stroke="{color}" stroke-width="2.5" points="{points}"/>')
    title = escape(str(report["symbol"]))
    return ('<svg viewBox="0 0 900 360" role="img" aria-label="收盘价与MA5 MA20">'
            f'<title>{title} 收盘价与移动平均线</title>'
            + "".join(paths)
            + f'<text x="54" y="340">{escape(report["dates"][0])}</text>'
            + f'<text x="846" y="340" text-anchor="end">{escape(report["dates"][-1])}</text>'
            + '</svg>')


def render_overlay_section(report):
    indicators = technical_summary(report)
    return ("<section><h2>收盘价与MA5、MA20趋势</h2>"
            + overlay_svg(report)
            + "<p>蓝线：收盘价；橙线：MA5；绿线：MA20。"
            + escape(indicators["observation"])
            + "。均线仅基于共同交易日期计算，数据不足不补值。"
            + "数据未获交易所官方认证；不构成交易信号。</p></section>")
