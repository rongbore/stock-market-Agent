"""Generate a read-only Chinese evidence summary from dual-source JSON artifacts."""
import argparse
import json
from datetime import date
import re
from pathlib import Path


def _disclosures(items, symbol, start_date, end_date):
    """Only metadata, never assert that a PDF or financial statement was read."""
    if not isinstance(items, list) or len(items) > 100:
        raise ValueError("disclosures must be a list of at most 100 entries")
    if not isinstance(start_date, str) or not isinstance(end_date, str):
        raise ValueError("research date range required for disclosures")
    try:
        start, end = date.fromisoformat(start_date), date.fromisoformat(end_date)
    except ValueError as exc:
        raise ValueError("invalid research date range") from exc
    if start.isoformat() != start_date or end.isoformat() != end_date or start > end:
        raise ValueError("invalid research date range")
    result = []
    for item in items:
        if not isinstance(item, dict) or item.get("symbol") != symbol:
            raise ValueError("disclosure symbol mismatch")
        day = item.get("announcement_date")
        title = item.get("title")
        if not isinstance(day, str) or not isinstance(title, str) or not title.strip():
            raise ValueError("invalid disclosure metadata")
        try:
            parsed = date.fromisoformat(day)
        except ValueError as exc:
            raise ValueError("invalid disclosure date") from exc
        if parsed.isoformat() != day or not start <= parsed <= end:
            raise ValueError("disclosure date outside research range")
        result.append({"date": day, "title": title})
    return sorted(result, key=lambda item: (item["date"], item["title"]))


def _fingerprints(items, symbol, start_date, end_date):
    if not isinstance(items, list) or len(items) > 100:
        raise ValueError("fingerprints must be a list of at most 100")
    if not isinstance(start_date, str) or not isinstance(end_date, str):
        raise ValueError("research dates required for fingerprints")
    try:
        start, end = date.fromisoformat(start_date), date.fromisoformat(end_date)
    except ValueError as exc:
        raise ValueError("invalid research dates") from exc
    if start.isoformat() != start_date or end.isoformat() != end_date or start > end:
        raise ValueError("invalid research dates")
    result = []
    for item in items:
        if not isinstance(item, dict) or item.get("symbol") != symbol:
            raise ValueError("fingerprint symbol mismatch")
        day, digest, size = (item.get("announcement_date"),
                             item.get("file_sha256"), item.get("file_size_bytes"))
        if not isinstance(day, str) or not re.fullmatch(r"[0-9]{4}-[0-9]{2}-[0-9]{2}", day):
            raise ValueError("invalid fingerprint date")
        try:
            parsed = date.fromisoformat(day)
        except ValueError as exc:
            raise ValueError("invalid fingerprint date") from exc
        if not start <= parsed <= end:
            raise ValueError("fingerprint outside research range")
        if not isinstance(digest, str) or not re.fullmatch(r"[0-9a-f]{64}", digest):
            raise ValueError("invalid SHA-256")
        if isinstance(size, bool) or not isinstance(size, int) or not 8 <= size <= 20 * 1024 * 1024:
            raise ValueError("invalid PDF size")
        if item.get("official_origin_verified") is not False or item.get("source_content_verified") is not False:
            raise ValueError("unsupported fingerprint verification claims")
        result.append((day, digest, size))
    return sorted(result)


def render(diag, comparison=None, disclosures=None, fingerprints=None):
    if not isinstance(diag, dict):
        raise ValueError("invalid diagnostics")
    comparison = comparison if isinstance(comparison, dict) else None
    agreed = bool(comparison and comparison.get("status") == "passed"
                  and comparison.get("cross_source_numerical_agreement") is True
                  and diag.get("status") == "success")
    coverage = comparison.get("date_coverage", {}) if comparison else {}
    # Only fixed labels from the pipeline; do not echo arbitrary error strings.
    def safe(value):
        value = " ".join(str(value).split())[:80]
        for char in ("\\", "[", "]", "<", ">", "*", "_", "`", "|", "!"):
            value = value.replace(char, "\\" + char)
        return value
    lines = [
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
    ]
    lines += ["## 公告索引元数据（可选、未核验正文）", ""]
    if disclosures is None:
        lines += ["- 未提供公告索引；不能推断该区间没有公告。", ""]
    else:
        items = _disclosures(disclosures, diag.get("symbol"), diag.get("start_date"), diag.get("end_date"))
        lines += [f"- 元数据条目数：{len(items)}；未核验公告原文、披露时刻或完整性。", ""]
        for item in items:
            lines.append(f"- {safe(item['date'])}：{safe(item['title'])}")
        lines.append("")
    lines += ["## 公告 PDF 文件指纹（可选、未认证）", ""]
    if fingerprints is None:
        lines += ["- 未提供公告 PDF 文件指纹；无法追溯本地原文文件。", ""]
    else:
        records = _fingerprints(fingerprints, diag.get("symbol"),
                                diag.get("start_date"), diag.get("end_date"))
        lines += [f"- 文件指纹条目数：{len(records)}；仅记录文件摘要，不证明官方来源或正文内容。", ""]
        for day, digest, size in records:
            lines.append(f"- {day}：SHA-256 \`{digest}\`；{size} 字节")
        lines.append("")
    return "\n".join(lines)


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument("--input-dir", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--disclosures-json", default=None)
    parser.add_argument("--fingerprints-json", default=None)
    args = parser.parse_args(argv)
    folder = Path(args.input_dir)
    diag = json.loads((folder / "dual_upstream_diagnostics.json").read_text(encoding="utf-8"))
    report_path = folder / "daily_crosscheck_report.json"
    comparison = json.loads(report_path.read_text(encoding="utf-8")) if report_path.exists() else None
    disclosures = json.loads(Path(args.disclosures_json).read_text(encoding="utf-8")) if args.disclosures_json else None
    fingerprints = json.loads(Path(args.fingerprints_json).read_text(encoding="utf-8")) if args.fingerprints_json else None
    target = Path(args.output)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(render(diag, comparison, disclosures, fingerprints), encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
