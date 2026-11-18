"""Export recomputed local batch research as a deterministic, inspectable ZIP."""
import argparse
import hashlib
from html import escape
from io import BytesIO
import os
from pathlib import Path
import tempfile
from zipfile import ZIP_STORED, ZipFile, ZipInfo

from scripts.batch_calendar_research import build_batch_calendar_research
from scripts.calendar_acceptance_cli import _load
from scripts.offline_batch_research_runner import _canonical_json_bytes


ITEM_LABELS = {"RESEARCH_GENERATED_UNVERIFIED": "已生成 · 未核验",
               "REVIEW_REQUIRED": "日期待核查", "FAILED_INPUT_OR_GENERATION": "输入或生成失败"}
BATCH_LABELS = {"ALL_RESEARCH_GENERATED_UNVERIFIED": "全部已生成 · 未核验",
                "PARTIAL_RESEARCH_UNVERIFIED": "部分已生成 · 未核验", "NO_RESEARCH_GENERATED": "未生成研究"}


def _index(batch):
    rows = []
    for entry in batch["results"]:
        symbol = entry["symbol"]  # Already validated by the raw batch contract.
        directory = "items/" + symbol
        page = (f'<a href="{escape(directory, quote=True)}/dashboard.html">查看研究页面</a>'
                if entry["status"] == "RESEARCH_GENERATED_UNVERIFIED" else "未生成研究页面")
        rows.append('<tr><td>' + escape(symbol) + '</td><td>' + escape(ITEM_LABELS[entry["status"]]) +
                    '</td><td>' + page + f' · <a href="{escape(directory, quote=True)}/diagnostic.json">诊断</a></td></tr>')
    return ('<!doctype html><html lang="zh-CN"><meta charset="utf-8">'
            '<meta name="viewport" content="width=device-width,initial-scale=1">'
            '<title>批量离线研究（未核验）</title><style>'
            'body{font:16px/1.7 system-ui,sans-serif;background:#f4f7fb;color:#20334a;margin:0}'
            'main{max-width:1080px;margin:auto;padding:28px}h1{font-size:28px}'
            '.notice{background:#fff2cc;padding:14px;border-radius:8px}'
            'table{width:100%;border-collapse:collapse;background:white}td,th{padding:12px;text-align:left;border-bottom:1px solid #dce3ed}'
            '.scroll{overflow-x:auto}a{color:#245a9c}code{overflow-wrap:anywhere}</style><main>'
            '<h1>批量离线研究（未核验）</h1><p class="notice">来源、历史可用性和日历真实性均未核验。'
            '日期匹配只针对调用方提供的日历；合成样例不是实际行情。各项可能使用不同日期，不构成选股排名或投资建议。</p>'
            f'<p>总任务：{batch["item_count"]}；已生成：{batch["generated_count"]}；'
            f'日期待核查：{batch["calendar_blocked_count"]}；失败：{batch["failed_count"]}。</p>'
            '<p>批次状态：<code>' + escape(BATCH_LABELS[batch["status"]]) + '</code></p>'
            '<p><a href="summary.md">中文汇总</a> · <a href="batch-result.json">完整结果</a> · '
            '<a href="manifest.json">文件校验清单</a></p><div class="scroll"><table>'
            '<thead><tr><th>股票</th><th>状态</th><th>材料</th></tr></thead><tbody>' + ''.join(rows) +
            '</tbody></table></div><p>本包仅供离线复核；文件哈希不能证明来源真实性。失败项不提供研究页面。</p></main></html>')


def build_batch_research_package(config):
    """Build only from raw configs; never trust caller-supplied batch outcomes."""
    batch = build_batch_calendar_research(config)
    files = {"index.html": _index(batch).encode("utf-8"),
             "summary.md": batch["summary_markdown"].encode("utf-8"),
             "batch-result.json": _canonical_json_bytes(batch) + b"\n"}
    for entry in batch["results"]:
        prefix = "items/" + entry["symbol"] + "/"
        diagnostic = {key: value for key, value in entry.items() if key != "result"}
        if "result" in entry:
            diagnostic["acceptance"] = entry["result"]["acceptance"]
        files[prefix + "diagnostic.json"] = _canonical_json_bytes(diagnostic) + b"\n"
        if entry["status"] == "RESEARCH_GENERATED_UNVERIFIED":
            files[prefix + "dashboard.html"] = entry["result"]["dashboard_html"].encode("utf-8")
    manifest = {"schema_version": "0.1", "status": batch["status"],
                "batch_input_sha256": batch["batch_input_sha256"],
                "batch_result_payload_sha256": batch["artifact_payload_sha256"],
                "item_count": batch["item_count"], "generated_count": batch["generated_count"],
                "calendar_blocked_count": batch["calendar_blocked_count"], "failed_count": batch["failed_count"],
                "source_content_verified": False, "historical_point_in_time_verified": False,
                "exchange_calendar_verified": False,
                "files": [{"path": name, "size_bytes": len(data), "sha256": hashlib.sha256(data).hexdigest()}
                          for name, data in sorted(files.items())]}
    files["manifest.json"] = _canonical_json_bytes(manifest) + b"\n"
    output = BytesIO()
    with ZipFile(output, "w", compression=ZIP_STORED) as archive:
        for name, data in sorted(files.items()):
            entry = ZipInfo(name, date_time=(1980, 1, 1, 0, 0, 0))
            entry.compress_type = ZIP_STORED
            entry.create_system = 3
            entry.external_attr = 0o100644 << 16
            archive.writestr(entry, data)
    return output.getvalue(), manifest


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", required=True, help="Explicit raw batch research config")
    parser.add_argument("--output", required=True, help="New ZIP file only")
    args = parser.parse_args(argv)
    output = Path(args.output)
    if output.exists() or output.is_symlink():
        raise FileExistsError("batch package output must be a new file")
    encoded, manifest = build_batch_research_package(_load(args.input))
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
    return 0 if manifest["status"] == "ALL_RESEARCH_GENERATED_UNVERIFIED" else 2


if __name__ == "__main__":
    raise SystemExit(main())
