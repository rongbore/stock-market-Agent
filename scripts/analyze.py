"""Run a single stock analysis without interactive prompts or broker access."""

import os
import re
import json
from datetime import date, datetime
from pathlib import Path
from zoneinfo import ZoneInfo

if __package__:
    from .provenance import build_manifest, save_manifest
    from .evidence_bundle import validate_evidence_bundle, save_evidence_bundle
    from .disclosure_candidates import screen_disclosures, save_disclosure_candidates
    from .official_disclosures import adapt_official_disclosure
else:
    from provenance import build_manifest, save_manifest
    from evidence_bundle import validate_evidence_bundle, save_evidence_bundle
    from disclosure_candidates import screen_disclosures, save_disclosure_candidates
    from official_disclosures import adapt_official_disclosure


def read_inputs():
    ticker = os.environ.get("ANALYSIS_TICKER", "NVDA").strip().upper()
    if not re.fullmatch(r"[A-Z0-9^][A-Z0-9.^=-]{0,31}", ticker):
        raise ValueError("股票代码格式错误，例如 NVDA、600519.SS、0700.HK")
    today = datetime.now(ZoneInfo("Asia/Shanghai")).date()
    raw_date = os.environ.get("ANALYSIS_DATE", "").strip()
    if raw_date:
        if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", raw_date):
            raise ValueError("分析日期必须使用 YYYY-MM-DD，例如 2026-11-04；不要省略月份或日期的前导零")
        try:
            trade_date = date.fromisoformat(raw_date)
        except ValueError as exc:
            raise ValueError("分析日期无效，请使用真实日历日期 YYYY-MM-DD") from exc
    else:
        trade_date = today
    if trade_date > today:
        raise ValueError("分析日期不能晚于北京时间当天")
    model = os.environ.get("ANALYSIS_MODEL", "deepseek-flash").strip()
    if not model:
        raise ValueError("模型 ID 不能为空")
    return ticker, trade_date.isoformat(), model


def load_disclosure_candidates(ticker, trade_date):
    """Validate optional local metadata before any paid model work begins."""
    disclosure_input = os.environ.get("ANALYSIS_DISCLOSURES_JSON", "").strip()
    if not disclosure_input:
        return None
    records = json.loads(Path(disclosure_input).read_text(encoding="utf-8"))
    official_source = os.environ.get("ANALYSIS_DISCLOSURE_SOURCE", "").strip().lower()
    if official_source:
        if not isinstance(records, list):
            raise ValueError("disclosures must be a list")
        records = [adapt_official_disclosure(item, source=official_source,
                                             analysis_date=trade_date)
                   for item in records]
    return screen_disclosures(records, analysis_date=trade_date, symbol=ticker)


def run_graph_with_diagnostics(graph, ticker, trade_date):
    try:
        return graph.propagate(ticker, trade_date)
    except ValueError as exc:
        if "Unexpected response type from OpenAI-compatible endpoint" not in str(exc):
            raise
        raise RuntimeError(
            "模型兼容接口返回了无法解析的响应，分析已停止；"
            "请核对模型 ID、API 提供方兼容性及上游服务状态。"
            "不要直接重复付费运行；先使用 dry_run 离线检查。"
            "FRED/新闻数据源缺失不一定是本次异常的直接原因。"
        ) from exc


def main():
    ticker, trade_date, model = read_inputs()
    candidates = load_disclosure_candidates(ticker, trade_date)
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
    state, _ = run_graph_with_diagnostics(graph, ticker, trade_date)
    report_file = graph.save_reports(state, ticker, html=True)
    report_dir = Path(report_file).resolve().parent
    expected_root = (root / "reports").resolve()
    if not report_dir.is_relative_to(expected_root):
        raise RuntimeError("报告路径不在预期的 results/reports 目录内")
    if not (report_dir / "complete_report.html").is_file():
        raise RuntimeError("分析完成但未生成预期 HTML 报告")
    manifest = build_manifest(
        ticker, trade_date, model, run_id=os.environ.get("GITHUB_RUN_ID")
    )
    provenance_path = save_manifest(report_dir, manifest)
    evidence_path = save_evidence_bundle(
        report_dir, validate_evidence_bundle([], analysis_date=trade_date)
    )
    if candidates is not None:
        candidate_path = save_disclosure_candidates(report_dir, candidates)
        print(f"未核实公告候选清单已保存：{candidate_path}")
    print(f"中文报告已保存：{report_dir}")
    print(f"运行元数据已保存：{provenance_path}")
    print(f"来源证据清单已保存（尚未接入真实来源）：{evidence_path}")
    if os.environ.get("GITHUB_STEP_SUMMARY"):
        with open(os.environ["GITHUB_STEP_SUMMARY"], "a", encoding="utf-8") as summary:
            summary.write(
                f"分析完成：`{ticker}`，日期 `{trade_date}`。\n\n"
                "请在本次运行的 Artifacts 下载报告，解压后打开 complete_report.html。\n"
            )


if __name__ == "__main__":
    main()
