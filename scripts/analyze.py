"""Run a single stock analysis without interactive prompts or broker access."""

import os
import re
from datetime import date, datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from provenance import build_manifest, save_manifest


def read_inputs():
    ticker = os.environ.get("ANALYSIS_TICKER", "NVDA").strip().upper()
    if not re.fullmatch(r"[A-Z0-9^][A-Z0-9.^=-]{0,31}", ticker):
        raise ValueError("股票代码格式错误，例如 NVDA、600519.SS、0700.HK")
    today = datetime.now(ZoneInfo("Asia/Shanghai")).date()
    raw_date = os.environ.get("ANALYSIS_DATE", "").strip()
    trade_date = date.fromisoformat(raw_date) if raw_date else today
    if trade_date > today:
        raise ValueError("分析日期不能晚于北京时间当天")
    model = os.environ.get("ANALYSIS_MODEL", "deepseek-flash").strip()
    if not model:
        raise ValueError("模型 ID 不能为空")
    return ticker, trade_date.isoformat(), model


def main():
    ticker, trade_date, model = read_inputs()
    if not os.environ.get("DEEPSEEK_API_KEY"):
        raise RuntimeError("请配置 GitHub Actions secret: DEEPSEEK_API_KEY")

    from tradingagents.default_config import DEFAULT_CONFIG
    from tradingagents.graph.trading_graph import TradingAgentsGraph

    root = Path("results").resolve()
    config = DEFAULT_CONFIG.copy()
    config.update(
        llm_provider="deepseek",
        quick_think_llm=model,
        deep_think_llm=model,
        output_language="简体中文",
        max_debate_rounds=1,
        max_risk_discuss_rounds=1,
        results_dir=str(root),
        data_cache_dir=str(root / "cache"),
        memory_log_path=str(root / "memory" / "trading_memory.md"),
    )
    graph = TradingAgentsGraph(
        selected_analysts=["market", "news", "fundamentals"], config=config
    )
    state, _ = graph.propagate(ticker, trade_date)
    report_file = graph.save_reports(state, ticker, html=True)
    report_dir = Path(report_file).parent
    if not (report_dir / "complete_report.html").is_file():
        raise RuntimeError("分析完成但未生成预期 HTML 报告")
    manifest = build_manifest(
        ticker, trade_date, model, run_id=os.environ.get("GITHUB_RUN_ID")
    )
    provenance_path = save_manifest(report_dir, manifest)
    print(f"中文报告已保存：{report_dir}")
    print(f"运行元数据已保存：{provenance_path}")
    if os.environ.get("GITHUB_STEP_SUMMARY"):
        with open(os.environ["GITHUB_STEP_SUMMARY"], "a", encoding="utf-8") as summary:
            summary.write(
                f"分析完成：`{ticker}`，日期 `{trade_date}`。\n\n"
                "请在本次运行的 Artifacts 下载报告，解压后打开 complete_report.html。\n"
            )


if __name__ == "__main__":
    main()
