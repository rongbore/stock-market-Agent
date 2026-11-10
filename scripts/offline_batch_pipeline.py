"""Compose the offline batch plan, runner and Chinese summary into one artifact."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import tempfile

from scripts.batch_research_plan import build_batch_plan
from scripts.batch_research_summary import render_summary, _unique_object
from scripts.offline_batch_research_runner import run_batch_plan, _canonical_json_bytes, MAX_INPUT_BYTES

INPUT_FIELDS = {"schema_version", "data_kind", "symbols", "analysis_date", "reports"}
DATA_LABELS = {"SYNTHETIC": "合成测试数据；不是实际市场数据。",
               "UNVERIFIED_LOCAL": "调用方提供的本地数据；来源尚未核验。"}


def build_pipeline(config, max_rows=20):
    """Run existing offline stages; retain exact deterministic intermediate objects."""
    encoded = _canonical_json_bytes(config)
    if type(config) is not dict or set(config) != INPUT_FIELDS:
        raise ValueError("pipeline input requires exact schema_version/data_kind/symbols/analysis_date/reports keys")
    if (config["schema_version"] != "0.1" or type(config["data_kind"]) is not str
            or config["data_kind"] not in DATA_LABELS):
        raise ValueError("unsupported pipeline version or data kind")
    plan = build_batch_plan(config["symbols"], config["analysis_date"])
    bundle = run_batch_plan(plan, config["reports"])
    summary = render_summary(bundle, max_rows=max_rows)
    payload = {"schema_version": "0.1", "data_kind_supplied_unverified": config["data_kind"],
               "pipeline_input_sha256": hashlib.sha256(encoded).hexdigest(),
               "hash_encoding": "json_sorted_keys_ascii_compact_v1",
               "summary_max_rows": max_rows, "plan": plan, "bundle": bundle,
               "summary_markdown": DATA_LABELS[config["data_kind"]] + "\n\n" + summary,
               "source_verified": False, "historical_point_in_time_verified": False,
               "is_prediction": False, "is_trading_advice": False}
    digest = hashlib.sha256(_canonical_json_bytes(payload)).hexdigest()
    return {**payload, "artifact_payload_sha256": digest}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", required=True, help="Bounded JSON with explicit symbols, date and inline reports")
    parser.add_argument("--output", required=True)
    parser.add_argument("--max-rows", type=int, default=20)
    args = parser.parse_args(argv)
    source, output = Path(args.input), Path(args.output)
    if output.is_symlink() or source.resolve() == output.resolve():
        raise ValueError("output cannot overwrite input or target a symbolic link")
    with source.open("rb") as stream:
        data = stream.read(MAX_INPUT_BYTES + 1)
    if len(data) > MAX_INPUT_BYTES:
        raise ValueError("pipeline input JSON too large")
    try:
        config = json.loads(data, object_pairs_hook=_unique_object)
    except (ValueError, UnicodeError, RecursionError) as exc:
        raise ValueError("invalid pipeline JSON") from exc
    artifact = build_pipeline(config, args.max_rows)
    # Serialize before touching output, so all stages succeed or the prior file survives.
    encoded = _canonical_json_bytes(artifact)
    output.parent.mkdir(parents=True, exist_ok=True)
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(mode="wb", dir=output.parent, delete=False) as stream:
            temporary = Path(stream.name)
            stream.write(encoded + b"\n")
        os.replace(temporary, output)
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
