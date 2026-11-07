"""Offline, evidence-bounded market research brief from existing trend reports.

No external requests, model calls, brokerage actions, or future-price predictions.
"""
import argparse
import json
import math
from pathlib import Path


def build_brief(report):
    if not isinstance(report, dict):
        raise ValueError("report must be object")
    symbol = report.get("symbol")
    dates = report.get("dates")
    prices = report.get("prices")
    if not isinstance(symbol, str) or not symbol.strip():
        raise ValueError("symbol missing")
    if not isinstance(dates, list) or not isinstance(prices, list) or not dates or len(dates) != len(prices):
        raise ValueError("unaligned evidence dates and prices")
    if dates != sorted(set(dates)):
        raise ValueError("dates must be unique and ascending")
    if any(isinstance(v, bool) or not isinstance(v, (int, float)) or not math.isfinite(v) or v <= 0 for v in prices):
        raise ValueError("invalid price evidence")
    agreement = report.get("numerical_agreement") is True
    change = (prices[-1] / prices[0] - 1) * 100 if len(prices) > 1 else None
    direction = ("上涨" if change > 0 else "下跌" if change < 0 else "持平") if change is not None else "无法判断"
    facts = [
        f"观察区间：{dates[0]} 至 {dates[-1]}，共有{len(dates)}个共同日期",
        f"最后一个共同日期的收盘价均值：{prices[-1]:.3f}元/股",
    ]
    if change is not None:
        facts.append(f"观察期价格{direction}，变化{change:+.2f}%")
    else:
        facts.append("仅有一个共同日期，无法计算区间涨跌幅")
    if agreement:
        facts.append("所附比较结果标记双源数值一致；不代表交易所认证")
    else:
        facts.append("双源数值一致性未确认，不应据此形成确定性判断")
    risks = [
        "行情来源内容及历史时点尚未获得官方核验",
        "历史价格变化不代表未来走势，不能据此推算目标价",
        "未提供经核验的财报、估值及公司事件，不能形成基本面结论",
    ]
    return {
        "schema_version": "0.1", "symbol": symbol,
        "evidence_window": {"start": dates[0], "end": dates[-1], "points": len(dates)},
        "historical_direction": direction,
        "research_stance": "证据不足，暂不形成方向性投资结论",
        "confidence": "不足以评估",
        "facts": facts[:5], "risks": risks,
        "missing_evidence": ["已核验的公司财报", "可追溯估值数据", "公司公告与事件时间线"],
        "source_verified": False, "official_verified": False,
        "is_prediction": False, "is_trading_advice": False,
    }


def render_markdown(brief):
    lines = [f'# {brief["symbol"]} 研究摘要（未核验）', "",
             f'**研究结论：** {brief["research_stance"]}', "",
             f'**置信度：** {brief["confidence"]}', "",
             "## 关键事实"]
    lines.extend(f"- {item}" for item in brief["facts"])
    lines += ["", "## 主要风险"]
    lines.extend(f"- {item}" for item in brief["risks"])
    lines += ["", "## 缺失证据"]
    lines.extend(f"- {item}" for item in brief["missing_evidence"])
    lines += ["", "仅供历史数据研究，不构成投资建议或交易指令。", ""]
    return "\n".join(lines)


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument("--trend-data", required=True)
    parser.add_argument("--output-dir", required=True)
    args = parser.parse_args(argv)
    report = json.loads(Path(args.trend_data).read_text(encoding="utf-8"))
    brief = build_brief(report)
    out = Path(args.output_dir)
    out.mkdir(parents=True, exist_ok=True)
    (out / "research_brief_unverified.json").write_text(json.dumps(brief, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    (out / "research_brief_unverified.md").write_text(render_markdown(brief), encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
