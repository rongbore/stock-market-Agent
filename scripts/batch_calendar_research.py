"""Run bounded, explicitly selected local calendar-gated research jobs."""
import argparse
import hashlib
import os
from pathlib import Path
import tempfile

from scripts.akshare_provider import _symbol
from scripts.calendar_acceptance_cli import _load, build_calendar_gated_research
from scripts.offline_batch_research_runner import _canonical_json_bytes

MAX_ITEMS = 20


def _sha(value):
    return hashlib.sha256(_canonical_json_bytes(value)).hexdigest()


def build_batch_calendar_research(config):
    """Isolate invalid jobs; do not turn partial generation into overall success."""
    input_hash = _sha(config)
    if type(config) is not dict or set(config) != {"schema_version", "items"} or config["schema_version"] != "0.1":
        raise ValueError("batch config requires schema_version and items")
    items = config["items"]
    if type(items) is not list or not 1 <= len(items) <= MAX_ITEMS:
        raise ValueError("batch requires 1 to 20 explicit jobs")
    seen = set()
    for item in items:
        if type(item) is not dict or set(item) != {"symbol", "config"}:
            raise ValueError("each job requires symbol and config")
        _symbol(item["symbol"])
        if item["symbol"] in seen:
            raise ValueError("duplicate job symbol")
        seen.add(item["symbol"])
    results = []
    for item in sorted(items, key=lambda item: item["symbol"]):
        raw = item["config"]
        entry = {"symbol": item["symbol"], "status": "FAILED_INPUT_OR_GENERATION",
                 "reason": "item_validation_or_generation_failed", "config_input_sha256": _sha(raw),
                 "snapshot_sha256": _sha(raw["snapshot"]) if type(raw) is dict and "snapshot" in raw else None,
                 "calendar_sha256": _sha(raw["calendar"]) if type(raw) is dict and "calendar" in raw else None,
                 "source_content_verified": False, "historical_point_in_time_verified": False,
                 "exchange_calendar_verified": False}
        try:
            if (type(raw) is not dict or type(raw.get("snapshot")) is not dict
                    or raw["snapshot"].get("symbol") != item["symbol"]):
                raise ValueError("job/snapshot symbol mismatch")
            result = build_calendar_gated_research(raw)
        except Exception:
            # Keep unrelated jobs runnable; never copy raw exception/provider bodies.
            results.append(entry)
            continue
        entry.update(status=result["status"], reason=None if result["status"] == "RESEARCH_GENERATED_UNVERIFIED"
                     else "calendar_date_mismatch", result=result)
        results.append(entry)
    generated = sum(r["status"] == "RESEARCH_GENERATED_UNVERIFIED" for r in results)
    blocked = sum(r["status"] == "REVIEW_REQUIRED" for r in results)
    failed = len(results) - generated - blocked
    status = ("ALL_RESEARCH_GENERATED_UNVERIFIED" if generated == len(results) else
              "PARTIAL_RESEARCH_UNVERIFIED" if generated else "NO_RESEARCH_GENERATED")
    summary = ["# 批量离线研究（未核验）", "", "仅处理显式提供的本地样本；不执行选股、联网或交易。",
               f"总任务：{len(results)}；已生成：{generated}；日期待核查：{blocked}；输入或生成失败：{failed}。", "",
               "| 股票 | 状态 | 原因 |", "| --- | --- | --- |"]
    summary.extend(f"| {r['symbol']} | {r['status']} | {r['reason'] or '-'} |" for r in results)
    payload = {"schema_version": "0.1", "status": status, "batch_input_sha256": input_hash,
               "hash_encoding": "json_sorted_keys_ascii_compact_v1", "item_count": len(results),
               "generated_count": generated, "calendar_blocked_count": blocked, "failed_count": failed,
               "results": results, "summary_markdown": "\n".join(summary) + "\n",
               "source_content_verified": False, "historical_point_in_time_verified": False,
               "exchange_calendar_verified": False,
               "limitations": ["No automatic selection, ranking or shared as-of date is inferred.",
                               "Each job retains its own supplied cutoff, calendar and unverified data declaration.",
                               "Date agreement does not establish authenticity or historical availability."]}
    return {**payload, "artifact_payload_sha256": _sha(payload)}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args(argv)
    output = Path(args.output)
    if output.exists() or output.is_symlink():
        raise FileExistsError("batch output must be a new file")
    artifact = build_batch_calendar_research(_load(args.input))
    encoded = _canonical_json_bytes(artifact) + b"\n"
    output.parent.mkdir(parents=True, exist_ok=True)
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(mode="wb", dir=output.parent, delete=False) as stream:
            temporary = Path(stream.name)
            stream.write(encoded)
        os.link(temporary, output)
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)
    return 0 if artifact["status"] == "ALL_RESEARCH_GENERATED_UNVERIFIED" else 2


if __name__ == "__main__":
    raise SystemExit(main())
