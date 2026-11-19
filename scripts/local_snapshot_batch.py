"""Build an offline batch ZIP from explicitly named local snapshot/calendar JSON."""
import argparse
import os
from pathlib import Path
import tempfile

from scripts.akshare_provider import _symbol
from scripts.backtest_data_contract import ADJUSTMENTS, _instant
from scripts.batch_calendar_research import MAX_ITEMS
from scripts.batch_research_package import build_batch_research_package
from scripts.calendar_acceptance_cli import _load
from scripts.offline_batch_research_runner import _canonical_json_bytes

FIELDS = {"schema_version", "data_kind", "evidence_as_of", "expected_adjustment", "items"}


def _relative(base, value):
    if type(value) is not str or not value or len(value) > 4096 or "\x00" in value:
        raise ValueError("input path must be a bounded relative string")
    path = Path(value)
    if path.is_absolute():
        raise ValueError("input path must be relative to the manifest")
    return base / path


def load_local_batch_config(manifest_path):
    """Return inline batch config and source paths, without authenticating paths."""
    manifest_path = Path(manifest_path)
    manifest = _load(manifest_path)
    _canonical_json_bytes(manifest)
    if type(manifest) is not dict or set(manifest) != FIELDS or manifest["schema_version"] != "0.1":
        raise ValueError("manifest requires exact fields")
    if type(manifest["data_kind"]) is not str or manifest["data_kind"] not in ("SYNTHETIC", "UNVERIFIED_LOCAL"):
        raise ValueError("unsupported data declaration")
    if type(manifest["expected_adjustment"]) is not str or manifest["expected_adjustment"] not in ADJUSTMENTS:
        raise ValueError("unsupported adjustment declaration")
    _instant(manifest["evidence_as_of"])
    items = manifest["items"]
    if type(items) is not list or not 1 <= len(items) <= MAX_ITEMS:
        raise ValueError("manifest requires 1 to 20 explicit items")
    seen, sources, requests = set(), [manifest_path], []
    for item in items:
        if type(item) is not dict or set(item) != {"symbol", "snapshot_path", "calendar_path"}:
            raise ValueError("manifest item requires symbol, snapshot_path and calendar_path")
        _symbol(item["symbol"])
        if item["symbol"] in seen:
            raise ValueError("duplicate manifest symbol")
        seen.add(item["symbol"])
        snapshot = _relative(manifest_path.parent, item["snapshot_path"])
        calendar = _relative(manifest_path.parent, item["calendar_path"])
        sources.extend((snapshot, calendar))
        requests.append((item["symbol"], snapshot, calendar))
    jobs = []
    for symbol, snapshot, calendar in requests:
        raw = {"schema_version": "0.1", "data_kind": manifest["data_kind"],
               "evidence_as_of": manifest["evidence_as_of"],
               "expected_adjustment": manifest["expected_adjustment"],
               "snapshot": _load(snapshot), "calendar": _load(calendar)}
        jobs.append({"symbol": symbol, "config": raw})
    config = {"schema_version": "0.1", "items": jobs}
    _canonical_json_bytes(config)
    return config, sources


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", required=True, help="Local manifest JSON; paths are relative to this file")
    parser.add_argument("--output", required=True, help="New ZIP file only")
    args = parser.parse_args(argv)
    output = Path(args.output)
    if output.exists() or output.is_symlink():
        raise FileExistsError("local batch output must be a new file")
    config, sources = load_local_batch_config(args.input)
    if output.resolve() in {source.resolve() for source in sources}:
        raise ValueError("output must not target a manifest or source file")
    encoded, manifest = build_batch_research_package(config)
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
