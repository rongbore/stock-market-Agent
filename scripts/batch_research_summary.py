"""Validate offline batch results and render a bounded Chinese review summary."""
import argparse
from datetime import date
import hashlib
import html
import json
import os
from pathlib import Path
import re
import tempfile

from scripts.batch_research_plan import build_batch_plan
from scripts.offline_batch_research_runner import _canonical_json_bytes, MAX_INPUT_BYTES

HASH = re.compile(r"[0-9a-f]{64}")
TOP_FIELDS = {"schema_version", "plan_id", "plan_sha256", "hash_encoding", "analysis_date",
              "job_count", "succeeded_count", "failed_count", "status", "results",
              "source_verified", "historical_point_in_time_verified", "is_prediction", "is_trading_advice"}
RESULT_FIELDS = {"job_id", "symbol", "source_verified", "brief", "input_sha256",
                 "input_hash_status", "status", "reason"}
BRIEF_FIELDS = {"schema_version", "symbol", "evidence_window", "historical_direction", "research_stance",
                "confidence", "facts", "risks", "missing_evidence", "source_verified", "official_verified",
                "is_prediction", "is_trading_advice"}
STATUS_TEXT = {"COMPLETED_UNVERIFIED": "摘要已生成（未核验）", "MISSING_INPUT": "缺少输入",
               "FAILED_INPUT_VALIDATION": "输入校验失败"}
REASONS = {"trend_report_not_supplied": "未提供趋势报告",
           "invalid_or_unbounded_json_input": "输入不是受支持的有界 JSON",
           "invalid_symbol_dates_or_prices": "股票代码、日期或价格校验失败"}


def _object(value, fields):
    if type(value) is not dict or set(value) != fields:
        raise ValueError("unexpected summary schema")


def _false_flags(value, flags):
    if any(value.get(flag) is not False for flag in flags):
        raise ValueError("summary cannot promote verification or advice flags")


def _day(value):
    if type(value) is not str:
        raise ValueError("invalid date")
    try:
        parsed = date.fromisoformat(value)
    except ValueError as exc:
        raise ValueError("invalid date") from exc
    if parsed.isoformat() != value:
        raise ValueError("noncanonical date")
    return parsed


def _hash(value):
    return type(value) is str and HASH.fullmatch(value) is not None


def validate_bundle(bundle):
    """Recount jobs and reconstruct plan binding; input hashes remain supplied IDs."""
    _canonical_json_bytes(bundle)
    _object(bundle, TOP_FIELDS)
    if bundle["schema_version"] != "0.1" or bundle["hash_encoding"] != "json_sorted_keys_ascii_compact_v1":
        raise ValueError("unsupported summary version or hash encoding")
    _false_flags(bundle, ("source_verified", "historical_point_in_time_verified", "is_prediction", "is_trading_advice"))
    results = bundle["results"]
    if type(results) is not list or not 1 <= len(results) <= 100:
        raise ValueError("invalid result count")
    for result in results:
        _object(result, RESULT_FIELDS)
    plan = build_batch_plan([result["symbol"] for result in results], bundle["analysis_date"])
    if (bundle["plan_id"] != plan["plan_id"] or not _hash(bundle["plan_sha256"])
            or bundle["plan_sha256"] != hashlib.sha256(_canonical_json_bytes(plan)).hexdigest()):
        raise ValueError("invalid reconstructed plan hash")
    successes = 0
    for result, job in zip(results, plan["jobs"]):
        if result["symbol"] != job["symbol"] or result["job_id"] != job["job_id"]:
            raise ValueError("job order or identity mismatch")
        _false_flags(result, ("source_verified",))
        status, hash_status, digest = result["status"], result["input_hash_status"], result["input_sha256"]
        if type(status) is not str or status not in STATUS_TEXT:
            raise ValueError("invalid job status")
        if status == "MISSING_INPUT":
            valid = hash_status == "missing" and digest is None and result["reason"] == "trend_report_not_supplied"
        elif status == "FAILED_INPUT_VALIDATION":
            valid = ((hash_status == "rejected_noncanonical_json" and digest is None
                      and result["reason"] == "invalid_or_unbounded_json_input")
                     or (hash_status == "canonical_json_sha256" and _hash(digest)
                         and result["reason"] == "invalid_symbol_dates_or_prices"))
        else:
            valid = hash_status == "canonical_json_sha256" and _hash(digest) and result["reason"] is None
        if not valid:
            raise ValueError("inconsistent job hash or reason")
        if status != "COMPLETED_UNVERIFIED":
            if result["brief"] is not None:
                raise ValueError("failed jobs cannot carry successful briefs")
            continue
        successes += 1
        brief = result["brief"]
        _object(brief, BRIEF_FIELDS)
        _false_flags(brief, ("source_verified", "official_verified", "is_prediction", "is_trading_advice"))
        if (brief["symbol"] != result["symbol"] or brief["schema_version"] != "0.1"
                or brief["historical_direction"] not in ("上涨", "下跌", "持平", "无法判断")
                or brief["research_stance"] != "证据不足，暂不形成方向性投资结论"
                or brief["confidence"] != "不足以评估"):
            raise ValueError("unsupported brief conclusion")
        window = brief["evidence_window"]
        _object(window, {"start", "end", "points"})
        start, end, cutoff = _day(window["start"]), _day(window["end"]), _day(bundle["analysis_date"])
        points = window["points"]
        if (type(points) is not int or not 1 <= points <= 10000 or not start <= end <= cutoff
                or (points == 1) != (start == end)):
            raise ValueError("invalid evidence window")
        for field, count in (("facts", 5), ("risks", 10), ("missing_evidence", 10)):
            values = brief[field]
            if (type(values) is not list or not 1 <= len(values) <= count
                    or any(type(text) is not str or not text.strip() or len(text) > 2000 for text in values)):
                raise ValueError("invalid brief text collection")
    expected_status = "COMPLETED_UNVERIFIED" if successes == len(results) else "COMPLETED_WITH_FAILURES"
    if (any(type(bundle[field]) is not int for field in ("job_count", "succeeded_count", "failed_count"))
            or (bundle["job_count"], bundle["succeeded_count"], bundle["failed_count"])
            != (len(results), successes, len(results) - successes)
            or bundle["status"] != expected_status):
        raise ValueError("inconsistent bundle counts or status")
    return bundle


def _escape(text, limit=160):
    text = " ".join(text.split())
    omitted = max(0, len(text) - limit)
    text = text[:limit]
    text = "".join(character if character.isprintable() else " " for character in text)
    text = html.escape(text, quote=True)
    text = re.sub(r"([\\`*_{}\[\]()#+\-.!|>~])", r"\\\1", text)
    return text + (f"（省略 {omitted} 字）" if omitted else "")


def render_summary(bundle, max_rows=20):
    validate_bundle(bundle)
    if type(max_rows) is not int or not 1 <= max_rows <= 100:
        raise ValueError("max_rows must be 1 to 100")
    lines = ["# 批量研究结果摘要（未核验）", "",
             f"分析截止日期：{bundle['analysis_date']}。共 {bundle['job_count']} 项；摘要生成成功 {bundle['succeeded_count']} 项，失败或缺失 {bundle['failed_count']} 项。",
             "", "成功仅表示本地历史摘要生成；来源、价格和历史时点均未核实，不构成排名、目标价或投资建议。", "",
             f"计划 ID：`{bundle['plan_id']}`", f"计划 SHA-256：`{bundle['plan_sha256']}`", "",
             "哈希仅标识解析后 JSON 的完整性，不证明发布者真实性。输入原件未随本摘要重新核对；计划哈希已按股票集合和日期重建检查。", "",
             "| 股票 | 处理结果 | 输入 SHA-256 |", "| --- | --- | --- |"]
    shown = bundle["results"][:max_rows]
    for result in shown:
        digest = result["input_sha256"] or ("缺失输入" if result["input_hash_status"] == "missing" else "无法生成有界 JSON 哈希")
        lines.append(f"| {_escape(result['symbol'])} | {STATUS_TEXT[result['status']]} | {digest} |")
    lines += ["", f"显示 {len(shown)} 项，省略 {len(bundle['results']) - len(shown)} 项；表格按计划代码顺序排列，不代表优先级。"]
    for result in shown:
        lines += ["", f"## {_escape(result['symbol'])}", ""]
        if result["brief"] is None:
            lines.append(f"失败原因：{REASONS[result['reason']]}。")
            continue
        brief = result["brief"]
        lines.append(f"历史方向：{brief['historical_direction']}。研究结论：{brief['research_stance']}。")
        lines.append("")
        lines.extend(f"- {_escape(fact)}" for fact in brief["facts"][:3])
        lines.append(f"事实显示 {min(3, len(brief['facts']))} 条，省略 {max(0, len(brief['facts']) - 3)} 条。")
    return "\n".join(lines) + "\n"


def _unique_object(pairs):
    value = {}
    for key, item in pairs:
        if key in value:
            raise ValueError("duplicate JSON key")
        value[key] = item
    return value


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--max-rows", type=int, default=20)
    args = parser.parse_args(argv)
    source, output = Path(args.input), Path(args.output)
    if output.is_symlink() or source.resolve() == output.resolve():
        raise ValueError("output cannot overwrite input or target a symbolic link")
    with source.open("rb") as stream:
        raw = stream.read(MAX_INPUT_BYTES + 1)
    if len(raw) > MAX_INPUT_BYTES:
        raise ValueError("input JSON too large")
    try:
        bundle = json.loads(raw, object_pairs_hook=_unique_object)
    except (ValueError, RecursionError, UnicodeError) as exc:
        raise ValueError("invalid summary JSON") from exc
    summary = render_summary(bundle, args.max_rows)
    output.parent.mkdir(parents=True, exist_ok=True)
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", dir=output.parent, delete=False) as stream:
            temporary = Path(stream.name)
            stream.write(summary)
        os.replace(temporary, output)
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
