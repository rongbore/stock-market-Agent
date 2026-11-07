"""Build a compact, offline price-trend chart report from two market snapshots.

This module never fetches data, calls an LLM, or places orders. Two-source
agreement is reported only as numerical agreement, never official verification.
"""
import argparse
import html
import json
import math
from datetime import date
from pathlib import Path
from scripts.trend_chart_overlay import render_overlay_section
from scripts.trend_indicators import technical_summary


def _validate_snapshot(snapshot):
    if not isinstance(snapshot, dict):
        raise ValueError("snapshot must be an object")
    symbol = snapshot.get("symbol")
    if not isinstance(symbol, str) or not symbol.strip():
        raise ValueError("snapshot symbol missing")
    if snapshot.get("price_unit") != "CNY_per_share":
        raise ValueError("price unit must be CNY_per_share")
    if snapshot.get("adjust") not in ("", "qfq", "hfq"):
        raise ValueError("unsupported adjustment mode")
    records = snapshot.get("records")
    if not isinstance(records, list) or not 1 <= len(records) <= 100000:
        raise ValueError("snapshot records missing or out of bounds")
    result = {}
    for row in records:
        if not isinstance(row, dict):
            raise ValueError("invalid row")
        day, close = row.get("date"), row.get("close")
        if not isinstance(day, str):
            raise ValueError("invalid date")
        try:
            parsed = date.fromisoformat(day)
        except ValueError as exc:
            raise ValueError("invalid date") from exc
        if parsed.isoformat() != day:
            raise ValueError("date must use YYYY-MM-DD")
        if day in result:
            raise ValueError("duplicate date")
        if isinstance(close, bool) or not isinstance(close, (int, float)) or not math.isfinite(close) or close <= 0:
            raise ValueError("invalid close price")
        result[day] = float(close)
    return symbol, snapshot["adjust"], result


def build_report(primary, secondary, comparison=None):
    sym_a, adj_a, a = _validate_snapshot(primary)
    sym_b, adj_b, b = _validate_snapshot(secondary)
    if sym_a != sym_b or adj_a != adj_b:
        raise ValueError("snapshot symbol or adjustment mismatch")
    shared = sorted(a.keys() & b.keys())
    if not shared:
        raise ValueError("no shared dates for chart")
    # Plot only dates present in both snapshots; do not fill gaps with zero.
    values = [(day, (a[day] + b[day]) / 2) for day in shared]
    values.sort(key=lambda item: item[0])
    prices = [value for _, value in values]
    change = (prices[-1] / prices[0] - 1) * 100 if len(prices) > 1 else None
    window = min(5, len(prices))
    ma = sum(prices[-window:]) / window
    trend = "数据不足，暂不判断" if len(prices) < 5 else (
        "观察期上涨" if prices[-1] > prices[0] else
        "观察期下跌" if prices[-1] < prices[0] else "观察期持平")
    agreed = bool(
        isinstance(comparison, dict)
        and comparison.get("status") == "passed"
        and comparison.get("cross_source_numerical_agreement") is True
        and comparison.get("independent_source_verified") is False
    )
    return {
        "symbol": sym_a, "adjust": adj_a, "dates": [x[0] for x in values],
        "prices": prices, "shared_points": len(values), "start_price": prices[0],
        "end_price": prices[-1], "change_pct": change, "last_ma": ma,
        "trend": trend, "numerical_agreement": agreed,
        "sources": [primary.get("upstream", "unknown"), secondary.get("upstream", "unknown")],
        "source_verified": False, "official_verified": False,
    }


def _svg(report):
    values = report["prices"]
    width, height, pad = 900, 360, 54
    lo, hi = min(values), max(values)
    span = hi - lo or max(abs(hi) * 0.02, 1)
    coords = []
    for i, value in enumerate(values):
        x = pad + (width - 2 * pad) * (i / max(1, len(values) - 1))
        y = height - pad - (value - lo) / span * (height - 2 * pad)
        coords.append((x, y))
    points = " ".join(f"{x:.1f},{y:.1f}" for x, y in coords)
    first, last = coords[0], coords[-1]
    return (f'<svg viewBox="0 0 {width} {height}" role="img" aria-label="收盘价折线图">'
            f'<line x1="{pad}" y1="{height-pad}" x2="{width-pad}" y2="{height-pad}" stroke="#888"/>'
            f'<line x1="{pad}" y1="{pad}" x2="{pad}" y2="{height-pad}" stroke="#888"/>'
            f'<polyline fill="none" stroke="#2563eb" stroke-width="3" points="{points}"/>'
            f'<circle cx="{first[0]:.1f}" cy="{first[1]:.1f}" r="5" fill="#2563eb"/>'
            f'<circle cx="{last[0]:.1f}" cy="{last[1]:.1f}" r="5" fill="#2563eb"/>'
            f'<text x="{pad}" y="{height-14}" font-size="14">{html.escape(report["dates"][0])}</text>'
            f'<text x="{width-pad}" y="{height-14}" text-anchor="end" font-size="14">{html.escape(report["dates"][-1])}</text>'
            f'<text x="{pad}" y="26" font-size="14">CNY/股 · {html.escape(report["adjust"] or "未复权")}</text>'
            f'</svg>')


def render_html(report):
    change = "数据不足" if report["change_pct"] is None else f'{report["change_pct"]:+.2f}%'
    body = (f'<h1>{html.escape(report["symbol"])} 价格趋势</h1>'
            f'<p>区间：{report["dates"][0]} 至 {report["dates"][-1]}；'
            f'共同日期：{report["shared_points"]}；双源数值一致性：'
            f'{"通过（非官方认证）" if report["numerical_agreement"] else "未通过或未完成"}。</p>'
            f'<h2>收盘价变化</h2>{render_overlay_section(report)}'
            f'<h2>核心要点</h2><ul><li>观察期变化：{change}</li>'
            f'<li>最新价格：{report["end_price"]:.3f} CNY/股</li>'
            f'<li>最近最多 5 个共同交易日均价：{report["last_ma"]:.3f} CNY/股</li>'
            f'<li>技术观察：{html.escape(report["trend"])}；不构成基本面或买卖建议。</li></ul>'
            f'<h2>证据边界</h2><p>来源：{html.escape(", ".join(report["sources"]))}。'
            '双源一致性不代表交易所认证；来源内容及历史时点均未核验。'
            '该图仅使用两个快照共同存在的日期，未对缺失日期补零或插值。</p>')
    return '<!doctype html><html lang="zh-CN"><meta charset="utf-8"><title>价格趋势报告</title><body>' + body + '</body></html>'


def render_markdown(report):
    indicators = technical_summary(report)
    change = "数据不足" if report["change_pct"] is None else f'{report["change_pct"]:+.2f}%'
    lines = [
        f'# {report["symbol"]} 价格趋势', "",
        f'- 区间：{report["dates"][0]} 至 {report["dates"][-1]}',
        f'- 共同交易日期：{report["shared_points"]}',
        f'- 双源数值一致性：{"通过（非官方认证）" if report["numerical_agreement"] else "未通过或未完成"}',
        "", "## 核心要点", "",
        f'- 观察期价格变化：{change}',
        f'- 最新收盘价：{report["end_price"]:.3f} CNY/股',
        f'- 最近最多 5 个共同交易日均价：{report["last_ma"]:.3f} CNY/股',
        f'- 技术观察：{report["trend"]}；{indicators['observation']}；仅描述观察期，不代表未来走势。',
        "", "## 折线图数据", "", "| 日期 | 双源收盘价均值（CNY/股） |", "|---|---:|",
    ]
    lines.extend(f"| {day} | {price:.3f} |" for day, price in zip(report["dates"], report["prices"]))
    lines += ["", "## MA5 / MA20 历史均线", "", "| 日期 | MA5 | MA20 |", "|---|---:|---:|"]
    for day, ma5, ma20 in zip(report["dates"], indicators["ma5"], indicators["ma20"]):
        a = f"{ma5:.3f}" if ma5 is not None else "数据不足"
        b = f"{ma20:.3f}" if ma20 is not None else "数据不足"
        lines.append(f"| {day} | {a} | {b} |")
    lines += ["", "## 数据边界", "",
              f'- 上游：{", ".join(report["sources"])}；双源数值一致不等于官方认证。',
              "- 未核验来源内容及历史时点；缺失日期不补零、不插值。",
              "- 当前只提供行情趋势观察，不生成基本面投资建议或确定性目标价。", ""]
    return "\n".join(lines)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--primary", required=True)
    parser.add_argument("--secondary", required=True)
    parser.add_argument("--comparison")
    parser.add_argument("--output-dir", required=True)
    args = parser.parse_args(argv)
    primary = json.loads(Path(args.primary).read_text(encoding="utf-8"))
    secondary = json.loads(Path(args.secondary).read_text(encoding="utf-8"))
    comparison = json.loads(Path(args.comparison).read_text(encoding="utf-8")) if args.comparison else None
    report = build_report(primary, secondary, comparison)
    out = Path(args.output_dir)
    out.mkdir(parents=True, exist_ok=True)
    (out / "price_trend_report.html").write_text(render_html(report), encoding="utf-8")
    (out / "price_trend_report.md").write_text(render_markdown(report), encoding="utf-8")
    (out / "price_trend_data.json").write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"Trend report generated for {report['symbol']} ({report['shared_points']} shared dates)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
