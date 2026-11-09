"""Render an unverified table review package for human inspection."""
import argparse
import html
import json
import os
from pathlib import Path
import tempfile

from scripts.financial_table_review_annotations import review_package_sha256, record_table_reviews


def _cell(value):
    if value is None:
        return "未知"
    text = " ".join(str(value).split())
    if len(text) > 180:
        text = text[:180] + "…"
    text = html.escape(text, quote=True)
    for token in ("\\", "|", "[", "]", "*", "_", "`", "!"):
        text = text.replace(token, "\\" + token)
    return text


def render_review_markdown(package, annotations=None, *, max_rows=100):
    """Show bounded rows and full pending counts; reviewer labels are assertions."""
    if type(max_rows) is not int or not 1 <= max_rows <= 500:
        raise ValueError("max_rows must be from 1 to 500")
    digest = review_package_sha256(package)
    if annotations is None:
        annotations = {"file_sha256": package["file_sha256"], "package_sha256": digest, "decisions": []}
    review = record_table_reviews(package, annotations)
    lines = ["# 财报表格复核材料（未核验）", "",
             f"PDF SHA-256：{package['file_sha256']}",
             f"复核包 SHA-256：{digest}", "",
             f"候选总数：{package['candidate_count']}；已记录决定：{review['decided_count']}；"
             f"待记录决定：{review['pending_count']}。", "",
             "复核决定由调用方提供，审核人身份未认证。接受某项不代表数值、来源、期间或合并口径已核实。",
             "原始阻断项全部保留；该材料不构成发布或合并授权。", "",
             "| 候选 | 原始数值 | 页/表/行/列（表行列从0开始） | 指标提示 | 单位提示 | 期间提示 | 阻断项 | 复核决定 |",
             "| --- | --- | --- | --- | --- | --- | --- | --- |"]
    for index, candidate in enumerate(package["candidates"][:max_rows]):
        if not isinstance(candidate, dict) or not isinstance(candidate.get("cell"), dict):
            raise ValueError("candidate cell required")
        cell = candidate["cell"]
        blockers = candidate.get("review_blockers")
        if not isinstance(blockers, list) or any(not isinstance(x, str) for x in blockers):
            raise ValueError("candidate blockers required")
        row = [index, cell.get("text"), "/".join(str(cell.get(key, "?")) for key in
                ("page", "table_index", "row_index", "column_index")),
               candidate.get("metric_hint_unverified"), candidate.get("unit_hint_unverified"),
               candidate.get("period_hint_unverified"), ", ".join(blockers),
               review["decisions"][index]["decision"]]
        lines.append("| " + " | ".join(_cell(value) for value in row) + " |")
    omitted = len(package["candidates"]) - min(max_rows, len(package["candidates"]))
    lines.extend(["", f"未展示候选：{omitted}。总数与待复核数量包含所有候选。",
                  "坐标、表头和指标名片段请查看与上述哈希一致的原始 JSON 及 PDF。", ""])
    return "\n".join(lines)


def _load(path):
    with Path(path).open("rb") as stream:
        raw = stream.read(5 * 1024 * 1024 + 1)
    if len(raw) > 5 * 1024 * 1024:
        raise ValueError("review JSON too large")
    return json.loads(raw)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--package", required=True)
    parser.add_argument("--annotations")
    parser.add_argument("--max-rows", type=int, default=100)
    parser.add_argument("--output", required=True)
    args = parser.parse_args(argv)
    output = Path(args.output)
    sources = [Path(args.package)] + ([Path(args.annotations)] if args.annotations else [])
    if output.is_symlink() or output.resolve() in [source.resolve() for source in sources]:
        raise ValueError("output must not overwrite review inputs")
    text = render_review_markdown(_load(args.package), _load(args.annotations) if args.annotations else None,
                                  max_rows=args.max_rows)
    output.parent.mkdir(parents=True, exist_ok=True)
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", dir=output.parent, delete=False) as stream:
            temporary = Path(stream.name)
            stream.write(text)
        os.replace(temporary, output)
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
