"""Export recomputed calendar-gated research as a deterministic local ZIP."""
import argparse
import hashlib
from io import BytesIO
import os
from pathlib import Path
import tempfile
from zipfile import ZIP_STORED, ZipFile, ZipInfo

from scripts.calendar_acceptance_cli import _load, build_calendar_gated_research
from scripts.offline_batch_research_runner import _canonical_json_bytes


NOTICE = ("离线研究包：来源、历史可用性和日历真实性均未核验。\n"
          "日期匹配只针对调用方提供的日历；合成样例不是实际行情。\n"
          "文件哈希用于检查内容是否一致，不能证明真实性。\n"
          "无交易操作，不构成投资建议。\n")


def build_research_package(config):
    """Recompute from raw input; no caller-provided successful record is trusted."""
    result = build_calendar_gated_research(config)
    files = {"acceptance.json": _canonical_json_bytes(result["acceptance"]) + b"\n"}
    generated = result["status"] == "RESEARCH_GENERATED_UNVERIFIED"
    readme = NOTICE + ("\n打开 dashboard.html 查看页面，summary.md 查看中文摘要。\n"
                       if generated else "\n日期检查未通过：请查看 acceptance.json，未生成研究或页面。\n")
    files["README.txt"] = readme.encode("utf-8")
    if generated:
        files.update({"research.json": _canonical_json_bytes(result["research"]) + b"\n",
                      "batch-config.json": _canonical_json_bytes(result["batch_config"]) + b"\n",
                      "summary.md": result["research"]["summary_markdown"].encode("utf-8"),
                      "dashboard.html": result["dashboard_html"].encode("utf-8")})
    manifest = {"schema_version": "0.1", "status": result["status"],
                "data_kind_supplied_unverified": config["data_kind"],
                "config_input_sha256": result["acceptance"]["config_input_sha256"],
                "gated_result_payload_sha256": result["artifact_payload_sha256"],
                "source_content_verified": False, "historical_point_in_time_verified": False,
                "exchange_calendar_verified": False,
                "files": [{"path": name, "size_bytes": len(data),
                           "sha256": hashlib.sha256(data).hexdigest()}
                          for name, data in sorted(files.items())]}
    files["manifest.json"] = _canonical_json_bytes(manifest) + b"\n"
    stream = BytesIO()
    with ZipFile(stream, "w", compression=ZIP_STORED) as archive:
        for name, data in sorted(files.items()):
            entry = ZipInfo(name, date_time=(1980, 1, 1, 0, 0, 0))
            entry.compress_type = ZIP_STORED
            entry.create_system = 3
            entry.external_attr = 0o100644 << 16
            archive.writestr(entry, data)
    return stream.getvalue(), manifest


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", required=True, help="Raw calendar acceptance config")
    parser.add_argument("--output", required=True, help="New ZIP file only")
    args = parser.parse_args(argv)
    output = Path(args.output)
    if output.exists() or output.is_symlink():
        raise FileExistsError("package output must be a new file")
    encoded, manifest = build_research_package(_load(args.input))
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
    return 0 if manifest["status"] == "RESEARCH_GENERATED_UNVERIFIED" else 2


if __name__ == "__main__":
    raise SystemExit(main())
