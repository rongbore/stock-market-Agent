"""Environment-only entry point for manually dispatched research Actions."""
from contextlib import redirect_stderr, redirect_stdout
import json
import os
from pathlib import Path
import re
from zipfile import ZipFile

from scripts.akshare_provider import _symbol
from scripts.market_date_window import resolve_market_window
from scripts.quick_market_research import main as quick_main
from scripts.verify_research_package import verify_research_package

OUTPUT_DIRECTORY = Path("research-output")
SOURCE_NOTICE = ("来源内容已核验：否；历史可用性已核验：否；交易所日历已核验：否；独立来源已核验：否。")


ACTION_MESSAGES = {
    "no_research_package": "采集或日历准备未产生研究包。",
    "dependency_unavailable": "研究运行所需依赖不可用，本次未完成研究。",
    "output_or_execution_failed": "研究输出或执行发生错误，本次未完成研究。",
    "validation_failed": "研究输入或运行数据未通过校验，本次未完成研究。",
    "research_execution_failed": "研究执行失败，本次未完成研究。",
    "integrity_failed": "研究包完整性校验失败，本次研究包不予发布。",
    "all_generated_unverified": "全部研究已生成，来源仍未核验。",
    "partial_or_no_research_unverified": "存在待核查或失败项目，请查看逐股结果。",
}
ITEM_STATUS_LABELS = {"RESEARCH_GENERATED_UNVERIFIED": "已生成 · 未核验",
                      "REVIEW_REQUIRED": "日期待核查", "FAILED_INPUT_OR_GENERATION": "输入或生成失败"}
ITEM_REASON_LABELS = {"collection_failed": "供应商采集失败，未取得可用数据",
                      "snapshot_validation_failed": "快照结构、来源、时间或单位校验失败",
                      "item_validation_or_generation_failed": "输入校验或研究生成失败",
                      "calendar_date_mismatch": "返回日期与提供的日历不一致",
                      "none": "无阻断项；数据仍未核验", "unknown": "原因未分类，请查看诊断"}


def _action_result(reason, stage="execution", *, status="ACTION_FAILED"):
    return {"schema_version": "0.1", "status": status, "stage": stage,
            "reason": reason, "message": ACTION_MESSAGES[reason], "items": [],
            "source_content_verified": False, "historical_point_in_time_verified": False,
            "exchange_calendar_verified": False, "independent_source_verified": False}


def _exception_reason(error):
    if isinstance(error, ImportError):
        return "dependency_unavailable"
    if isinstance(error, OSError):
        return "output_or_execution_failed"
    if isinstance(error, ValueError):
        return "validation_failed"
    return "research_execution_failed"


def _item_results(batch, collection):
    rows = batch.get("results")
    if type(rows) is not list or not 1 <= len(rows) <= 5:
        raise ValueError("invalid action item results")
    collected = {}
    if collection is not None:
        entries = collection.get("items")
        if type(entries) is not list or len(entries) > 5:
            raise ValueError("invalid collection results")
        for entry in entries:
            _symbol(entry["symbol"])
            collected[entry["symbol"]] = entry
    items, seen = [], set()
    for row in rows:
        symbol, status = row["symbol"], row["status"]
        _symbol(symbol)
        if symbol in seen or status not in ITEM_STATUS_LABELS:
            raise ValueError("invalid action item")
        seen.add(symbol)
        reason = collected.get(symbol, {}).get("reason") or row.get("reason") or "none"
        reason = reason if type(reason) is str and reason in ITEM_REASON_LABELS else "unknown"
        if status == "REVIEW_REQUIRED":
            reason = "calendar_date_mismatch"
        elif status == "FAILED_INPUT_OR_GENERATION" and reason == "none":
            reason = "unknown"
        item = {"symbol": symbol, "status": status, "status_label": ITEM_STATUS_LABELS[status],
                "reason": reason, "reason_label": ITEM_REASON_LABELS[reason]}
        if status == "REVIEW_REQUIRED":
            coverage = row.get("result", {}).get("acceptance", {}).get("calendar_coverage", {})
            for key, name in (("missing_dates", "missing_date_count"), ("unexpected_dates", "unexpected_date_count")):
                dates = coverage.get(key, [])
                if type(dates) is not list or len(dates) > 367:
                    raise ValueError("invalid coverage count")
                item[name] = len(dates)
        items.append(item)
    return items


def _research_summary(manifest, items):
    text = (f'总任务：{manifest["item_count"]}；已生成：{manifest["generated_count"]}；'
            f'日期待核查：{manifest["calendar_blocked_count"]}；失败：{manifest["failed_count"]}。'
            '文件完整性通过；研究与来源仍未核验。')
    text += "\n\n| 股票 | 状态 | 原因 |\n| --- | --- | --- |\n"
    for item in items:
        reason = item["reason_label"]
        if "missing_date_count" in item:
            reason += f'；缺失日期：{item["missing_date_count"]}；额外日期：{item["unexpected_date_count"]}'
        text += f'| {item["symbol"]} | {item["status_label"]} | {reason} |\n'
    return text


class _Discard:
    def write(self, value):
        return len(value)

    def flush(self):
        pass


def _inputs():
    raw = os.environ.get("RESEARCH_SYMBOLS", "")
    upstream = os.environ.get("RESEARCH_UPSTREAM", "")
    start = os.environ.get("RESEARCH_START_DATE", "")
    end = os.environ.get("RESEARCH_END_DATE", "")
    if len(raw) > 200 or len(upstream) > 20 or len(start) > 10 or len(end) > 10:
        raise ValueError("input length")
    symbols = re.split(r"[,，\s]+", raw.strip())
    if not 1 <= len(symbols) <= 5 or len(set(symbols)) != len(symbols):
        raise ValueError("symbols count")
    for symbol in symbols:
        _symbol(symbol)
    if upstream not in ("sina", "eastmoney"):
        raise ValueError("upstream")
    window = resolve_market_window(start, end)
    return symbols, upstream, window


def _failure_verification():
    return {"schema_version": "0.1", "status": "INVALID_PACKAGE", "integrity_verified": False,
            "source_content_verified": False, "historical_point_in_time_verified": False,
            "exchange_calendar_verified": False, "independent_source_verified": False,
            "checked_file_count": 0, "checked_bytes": 0,
            "reason": "research_action_failed", "message": "本次研究未产生可发布的完整性通过包。",
            "limitation": "仅校验字节完整性，不认证来源或金融内容。"}


def _summary(message):
    text = "## 本次研究结果\n\n" + message + "\n\n" + SOURCE_NOTICE + "\n"
    print(text, end="")
    destination = os.environ.get("GITHUB_STEP_SUMMARY")
    if destination:
        try:
            with Path(destination).open("a", encoding="utf-8") as stream:
                stream.write(text)
        except OSError:
            print("无法写入步骤摘要；请查看本步骤固定结果消息。")


def _remove_package(package):
    try:
        package.unlink(missing_ok=True)
    except OSError:
        return False
    return True


def main():
    try:
        symbols, upstream, window = _inputs()
    except (ValueError, TypeError):
        _summary("输入无效：请提供 1–5 个不重复 A 股代码、明确的数据源及有效日期窗口。")
        return 2
    directory = OUTPUT_DIRECTORY
    try:
        if directory.is_symlink() or (directory.exists() and (not directory.is_dir() or any(directory.iterdir()))):
            _summary("输出目录必须全新或为空；本次未运行采集。")
            return 2
        directory.mkdir(exist_ok=True)
    except OSError:
        _summary("无法准备本次输出目录；本次未运行采集。")
        return 2
    package = directory / "research.zip"
    verification_path = directory / "verification.json"
    action_path = directory / "action-result.json"
    verification = _failure_verification()
    action = _action_result("no_research_package")
    message = action["message"]
    exit_code = 2
    stage = "execution"
    try:
        argv = ["--symbols", *symbols, "--upstream", upstream,
                "--start-date", window["start_date"], "--end-date", window["end_date"],
                "--allow-network", "--output", str(package)]
        # Third-party adapter logs and exception text must not reach Actions logs.
        with redirect_stdout(_Discard()), redirect_stderr(_Discard()):
            quick_exit = quick_main(argv)
        if quick_exit in (0, 2) and package.is_file() and not package.is_symlink():
            stage = "verification"
            verification = verify_research_package(package)
            if verification["integrity_verified"]:
                stage = "result_summary"
                with ZipFile(package) as archive:
                    manifest = json.loads(archive.read("manifest.json"))
                    batch = json.loads(archive.read("batch-result.json"))
                    collection = (json.loads(archive.read("collection.json"))
                                  if "collection.json" in archive.namelist() else None)
                items = _item_results(batch, collection)
                expected_counts = {"RESEARCH_GENERATED_UNVERIFIED": manifest["generated_count"],
                                   "REVIEW_REQUIRED": manifest["calendar_blocked_count"],
                                   "FAILED_INPUT_OR_GENERATION": manifest["failed_count"]}
                if (len(items) != manifest["item_count"] or any(
                        sum(item["status"] == status for item in items) != count
                        for status, count in expected_counts.items())):
                    raise ValueError("action item counts disagree with manifest")
                complete = (quick_exit == 0 and manifest["status"] == "ALL_RESEARCH_GENERATED_UNVERIFIED"
                            and manifest["generated_count"] == manifest["item_count"]
                            and manifest["calendar_blocked_count"] == manifest["failed_count"] == 0)
                action = _action_result("all_generated_unverified" if complete else "partial_or_no_research_unverified",
                                        "completed", status="ACTION_COMPLETED_UNVERIFIED" if complete else "ACTION_PARTIAL_UNVERIFIED")
                action.update({key: manifest[key] for key in
                               ("item_count", "generated_count", "calendar_blocked_count", "failed_count")})
                action["items"] = items
                message = _research_summary(manifest, items)
                if complete:
                    exit_code = 0
            else:
                action = _action_result("integrity_failed", "verification")
                message = action["message"]
    except (Exception, SystemExit) as error:
        action = _action_result(_exception_reason(error), stage)
        message = action["message"]
    try:
        if action["status"] == "ACTION_FAILED" and not _remove_package(package):
            raise OSError("cannot remove failed package")
        with verification_path.open("x", encoding="utf-8") as stream:
            stream.write(json.dumps(verification, ensure_ascii=False, sort_keys=True) + "\n")
        with action_path.open("x", encoding="utf-8") as stream:
            stream.write(json.dumps(action, ensure_ascii=False, sort_keys=True) + "\n")
        destination = os.environ.get("GITHUB_OUTPUT")
        if not destination:
            raise OSError("missing Actions output destination")
        with Path(destination).open("a", encoding="utf-8") as stream:
            stream.write("artifacts_ready=true\n")
    except OSError:
        # No ready flag is emitted for stale directories or failed publication.
        # A cleanup failure must not leak a traceback or allow artifact upload.
        _remove_package(package)
        message = "无法发布本次完整性结果，本次研究包不予发布。"
        exit_code = 2
    _summary(message)
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
