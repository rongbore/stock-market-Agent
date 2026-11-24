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
    verification = _failure_verification()
    message = "采集或日历准备失败，本次没有可发布的研究包。"
    exit_code = 2
    try:
        argv = ["--symbols", *symbols, "--upstream", upstream,
                "--start-date", window["start_date"], "--end-date", window["end_date"],
                "--allow-network", "--output", str(package)]
        # Third-party adapter logs and exception text must not reach Actions logs.
        with redirect_stdout(_Discard()), redirect_stderr(_Discard()):
            quick_exit = quick_main(argv)
        if quick_exit in (0, 2) and package.is_file() and not package.is_symlink():
            verification = verify_research_package(package)
            if verification["integrity_verified"]:
                with ZipFile(package) as archive:
                    manifest = json.loads(archive.read("manifest.json"))
                message = (f'总任务：{manifest["item_count"]}；已生成：{manifest["generated_count"]}；'
                           f'日期待核查：{manifest["calendar_blocked_count"]}；失败：{manifest["failed_count"]}。'
                           '文件完整性通过；研究与来源仍未核验。')
                if (quick_exit == 0 and manifest["status"] == "ALL_RESEARCH_GENERATED_UNVERIFIED"
                        and manifest["generated_count"] == manifest["item_count"]
                        and manifest["calendar_blocked_count"] == manifest["failed_count"] == 0):
                    exit_code = 0
            else:
                message = "研究包完整性校验失败，本次研究包不予发布。"
    except (Exception, SystemExit):
        verification = _failure_verification()
        message = "采集或日历准备失败，本次没有可发布的研究包。"
    try:
        if not verification["integrity_verified"] and not _remove_package(package):
            raise OSError("cannot remove failed package")
        with verification_path.open("x", encoding="utf-8") as stream:
            stream.write(json.dumps(verification, ensure_ascii=False, sort_keys=True) + "\n")
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
