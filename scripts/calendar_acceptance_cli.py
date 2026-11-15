"""Offline acceptance of explicit local snapshots against an unverified calendar."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import stat
import tempfile

from scripts.backtest_data_contract import build_backtest_dataset
from scripts.batch_research_summary import _unique_object
from scripts.market_calendar_coverage import check_calendar_coverage
from scripts.offline_batch_research_runner import MAX_INPUT_BYTES, _canonical_json_bytes

FIELDS = {"schema_version", "data_kind", "snapshot", "calendar", "evidence_as_of", "expected_adjustment"}


def _sha(value):
    return hashlib.sha256(_canonical_json_bytes(value)).hexdigest()


def build_calendar_acceptance(config):
    """Validate OHLCV first; date agreement never establishes source authenticity."""
    _canonical_json_bytes(config)
    if type(config) is not dict or set(config) != FIELDS:
        raise ValueError("calendar acceptance requires exact config fields")
    if (config["schema_version"] != "0.1" or type(config["data_kind"]) is not str
            or config["data_kind"] not in ("SYNTHETIC", "UNVERIFIED_LOCAL")):
        raise ValueError("unsupported schema or data declaration")
    snapshot = config["snapshot"]
    dataset = build_backtest_dataset(snapshot, evidence_as_of=config["evidence_as_of"],
                                     expected_adjustment=config["expected_adjustment"])
    coverage = check_calendar_coverage(config["calendar"], snapshot)
    payload = {"schema_version": "0.1", "status": coverage["status"],
               "data_kind_supplied_unverified": config["data_kind"],
               "config_input_sha256": _sha(config), "snapshot_sha256": _sha(snapshot),
               "hash_encoding": "json_sorted_keys_ascii_compact_v1",
               "symbol": dataset["symbol"], "upstream": dataset["provenance"]["upstream"],
               "evidence_as_of": dataset["evidence_as_of"], "adjustment": dataset["adjustment"],
               "requested_start": snapshot["start_date"], "requested_end": snapshot["end_date"],
               "calendar_coverage": coverage, "source_content_verified": False,
               "historical_point_in_time_verified": False, "exchange_calendar_verified": False,
               "limitations": ["Date agreement is only against the supplied unverified calendar.",
                               "Missing sessions may be suspensions and require review; no bars are filled.",
                               "Not proof of source authenticity or historical availability.",
                               "No returns, strategy performance or trading actions are computed."]}
    return {**payload, "artifact_payload_sha256": _sha(payload)}


def _load(path):
    flags = os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0) | getattr(os, "O_NONBLOCK", 0) | getattr(os, "O_BINARY", 0)
    descriptor = os.open(path, flags)
    with os.fdopen(descriptor, "rb") as stream:
        info = os.fstat(stream.fileno())
        if not stat.S_ISREG(info.st_mode) or info.st_size > MAX_INPUT_BYTES:
            raise ValueError("input must be a bounded regular JSON file")
        raw = stream.read(MAX_INPUT_BYTES + 1)
    if len(raw) > MAX_INPUT_BYTES:
        raise ValueError("input JSON too large")
    try:
        return json.loads(raw, object_pairs_hook=_unique_object)
    except (ValueError, UnicodeError, RecursionError) as exc:
        raise ValueError("invalid acceptance JSON") from exc


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args(argv)
    output = Path(args.output)
    if output.exists() or output.is_symlink():
        raise FileExistsError("acceptance output must be a new file")
    artifact = build_calendar_acceptance(_load(args.input))
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
    return 0 if artifact["status"] == "MATCH" else 2


if __name__ == "__main__":
    raise SystemExit(main())
