"""One deterministic offline chronological paper-evaluation artifact from explicit JSON."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import stat
import tempfile

from scripts.offline_batch_research_runner import MAX_INPUT_BYTES, _canonical_json_bytes
from scripts.sma_out_of_sample import evaluate_sma_out_of_sample

CONFIG_FIELDS = {"schema_version", "data_kind", "snapshot", "settings"}
SETTING_FIELDS = {"evidence_as_of", "expected_adjustment", "train_end", "test_start", "window",
                  "initial_cash", "board_lot_size", "commission_bps", "minimum_fee",
                  "sell_tax_bps", "slippage_bps"}
SNAPSHOT_FIELDS = {"schema_version", "symbol", "source", "upstream", "interface", "akshare_version",
                   "adjust", "price_unit", "volume_unit", "start_date", "end_date", "retrieved_at",
                   "source_content_verified", "historical_point_in_time_verified", "records"}
LABELS = {"SYNTHETIC": "SYNTHETIC TEST DATA: not actual market data or verified performance.",
          "UNVERIFIED_LOCAL": "Caller-supplied local data: origin and historical availability unverified."}
MAX_CONFIG_BARS = 500


def build_evaluation_artifact(config):
    """Enforce exact config keys; call existing evaluation with no financial changes."""
    encoded_input = _canonical_json_bytes(config)
    if type(config) is not dict or set(config) != CONFIG_FIELDS:
        raise ValueError("evaluation config requires exact schema_version/data_kind/snapshot/settings keys")
    if (config["schema_version"] != "0.1" or type(config["data_kind"]) is not str
            or config["data_kind"] not in LABELS):
        raise ValueError("unsupported config version or data_kind")
    settings, snapshot = config["settings"], config["snapshot"]
    if type(settings) is not dict or set(settings) != SETTING_FIELDS:
        raise ValueError("all evaluation settings, including every execution cost, must be explicit")
    if type(snapshot) is not dict or set(snapshot) != SNAPSHOT_FIELDS:
        raise ValueError("snapshot requires exact normalized AKShare metadata fields")
    version = snapshot["akshare_version"]
    if type(version) is not str or not version.strip() or len(version) > 100:
        raise ValueError("akshare_version must be a bounded explicit string")
    if type(snapshot["records"]) is not list or not 1 <= len(snapshot["records"]) <= MAX_CONFIG_BARS:
        raise ValueError("evaluation CLI supports 1 to 500 inline daily bars")
    evaluation = evaluate_sma_out_of_sample(snapshot, **settings)
    payload = {"schema_version": "0.1", "data_kind_supplied_unverified": config["data_kind"],
               "data_declaration": LABELS[config["data_kind"]],
               "config_input_sha256": hashlib.sha256(encoded_input).hexdigest(),
               "hash_encoding": "json_sorted_keys_ascii_compact_v1",
               "settings": dict(settings), "evaluation": evaluation,
               "source_content_verified": False, "historical_point_in_time_verified": False,
               "verified_performance": False, "is_trading_advice": False}
    return {**payload, "artifact_payload_sha256": hashlib.sha256(_canonical_json_bytes(payload)).hexdigest()}


def _unique_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("duplicate JSON key")
        result[key] = value
    return result


def _load_config(path):
    flags = (os.O_RDONLY | getattr(os, "O_BINARY", 0) | getattr(os, "O_NOFOLLOW", 0)
             | getattr(os, "O_NONBLOCK", 0))
    descriptor = os.open(path, flags)
    with os.fdopen(descriptor, "rb") as stream:
        info = os.fstat(stream.fileno())
        if not stat.S_ISREG(info.st_mode) or info.st_size > MAX_INPUT_BYTES:
            raise ValueError("config must be a bounded regular JSON file")
        raw = stream.read(MAX_INPUT_BYTES + 1)
    if len(raw) > MAX_INPUT_BYTES:
        raise ValueError("config JSON too large")
    try:
        return json.loads(raw, object_pairs_hook=_unique_object)
    except (ValueError, UnicodeError, RecursionError) as exc:
        raise ValueError("invalid evaluation JSON") from exc


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", required=True, help="Explicit inline snapshot, settings and data declaration")
    parser.add_argument("--output", required=True)
    args = parser.parse_args(argv)
    source, output = Path(args.input), Path(args.output)
    if (output.is_symlink() or source.resolve() == output.resolve()
            or (output.exists() and os.path.samefile(source, output))):
        raise ValueError("output must not overwrite config or target a symbolic link")
    artifact = build_evaluation_artifact(_load_config(source))
    encoded = _canonical_json_bytes(artifact) + b"\n"
    # All validation and serialization finish before an existing output is touched.
    output.parent.mkdir(parents=True, exist_ok=True)
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(mode="wb", dir=output.parent, delete=False) as stream:
            temporary = Path(stream.name)
            stream.write(encoded)
        if output.is_symlink():
            raise ValueError("output became a symbolic link")
        os.replace(temporary, output)
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
