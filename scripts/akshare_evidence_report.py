"""Generate a read-only Chinese evidence summary from dual-source JSON artifacts."""
import argparse
import json
from pathlib import Path


def render(diag, comparison=None):
    if not isinstance(diag, dict):
        raise ValueError("invalid diagnostics")
    comparison = comparison if isinstance(comparison, dict) else None
    agreed = bool(comparison and comparison.get("status") == "passed"
                  and comparison.get("cross_source_numerical_agreement") is True
                  and diag.get("status") == "success")
    coverage = comparison.get("date_coverage", {}) if comparison else {}
    # Only fixed labels from the pipeline; do not echo arbitrary error strings.
    def safe(value):
        return str(value).replace("|", " ").replace("\n", " ").replace("\r", " ")[:80]
    return "\n".join([
        "# A 股双来源行情研究证据（未认证）", "",
        "> 只读数据质量报告；非投资建议、交易信号或交易所权威认证。", "",
        "## 数据范围", "",
        "| 项目 | 内容 |", "|---|---|",
        f"| 股票代码 | {safe(diag.get('symbol', 'unknown'))} |",
        f"| 开始日期 | {safe(diag.get('start_date', 'unknown'))} |",
        f"| 结束日期 | {safe(diag.get('end_date', 'unknown'))} |",
        f"| 东方财富记录数 | {safe(diag.get('eastmoney_record_count', 0))} |",
        f"| 新浪记录数 | {safe(diag.get('sina_record_count', 0))} |",
        f"| 数值一致性 | {'容差内通过' if agreed else '未通过或未完成'} |",
        "| 官方数据认证 | 未认证 |", "",
        "## 来源与核验", "",
        "- 来源：AKShare 东方财富接口及新浪接口，均为非交易所认证的上游数据。",
        f"- 数值差异项：{safe(comparison.get('difference_count', '未知')) if comparison else '未执行比较'}。",
        f"- 共同交易日期：{safe(coverage.get('shared_trading_date_count', '未知'))}。",
        f"- 东方财富独有日期：{safe(coverage.get('primary_only_date_count', '未知'))}。",
        f"- 新浪独有日期：{safe(coverage.get('secondary_only_date_count', '未知'))}。",
        "- 官方交易日历：未核验；两源共同缺失的日期无法由此发现。", "",
        "## 风险、冲突与缺失", "",
        f"- 采集状态：{safe(diag.get('status', 'unknown'))}。",
        f"- 安全错误类别：{safe(diag.get('error_category') or '无')}。",
        f"- 东方财富错误类型：{safe(diag.get('eastmoney_error_kind') or '无')}。",
        f"- 新浪错误类型：{safe(diag.get('sina_error_kind') or '无')}。",
        "- 未核验财报、公告正文及历史披露时间，不作基本面结论。",
        "- 即使数值一致，也不证明数据真实、完整或在历史时点可获得。", "",
        "## 结论与下一步", "",
        "本次仅能证明所请求区间内的双源行情数值符合设定容差。"
        if agreed else "当前缺乏双源行情数值一致性证据。",
        "后续需补充官方交易日历、披露时间与公告原文核验。", "",
    ])


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument("--input-dir", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args(argv)
    folder = Path(args.input_dir)
    diag = json.loads((folder / "dual_upstream_diagnostics.json").read_text(encoding="utf-8"))
    report_path = folder / "daily_crosscheck_report.json"
    comparison = json.loads(report_path.read_text(encoding="utf-8")) if report_path.exists() else None
    target = Path(args.output)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(render(diag, comparison), encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
