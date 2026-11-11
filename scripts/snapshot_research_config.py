"""Convert explicit local AKShare snapshots to an unverified batch raw config."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import tempfile

from scripts.backtest_data_contract import _day, build_backtest_dataset
from scripts.batch_research_plan import build_batch_plan
from scripts.batch_research_summary import _unique_object
from scripts.offline_batch_research_runner import MAX_INPUT_BYTES, _canonical_json_bytes


def build_snapshot_research_config(config):
    """Reject invalid snapshots, keep source identities, infer no dual-source agreement."""
    _canonical_json_bytes(config)
    if type(config) is not dict or set(config) != {
            "schema_version", "data_kind", "analysis_date", "evidence_as_of", "expected_adjustment", "snapshots"}:
        raise ValueError("snapshot adapter requires exact input fields")
    if config["schema_version"] != "0.1" or config["data_kind"] not in ("SYNTHETIC", "UNVERIFIED_LOCAL"):
        raise ValueError("unsupported schema or data kind")
    day = _day(config["analysis_date"])
    snapshots = config["snapshots"]
    if type(snapshots) is not dict or not 1 <= len(snapshots) <= 100:
        raise ValueError("snapshots must map 1 to 100 symbols to objects")
    plan = build_batch_plan(list(snapshots), config["analysis_date"])
    reports = {}
    for symbol in plan["symbols"]:
        snapshot = snapshots[symbol]
        if type(snapshot) is not dict or snapshot.get("symbol") != symbol:
            raise ValueError("snapshot symbol mismatch")
        dataset = build_backtest_dataset(snapshot, evidence_as_of=config["evidence_as_of"],
                                         expected_adjustment=config["expected_adjustment"])
        bars = dataset["bars"]
        if len(bars) > 10000 or any(_day(bar["date"]) > day for bar in bars):
            raise ValueError("snapshot has too many bars or rows after analysis date")
        reports[symbol] = {
            "symbol": symbol, "dates": [bar["date"] for bar in bars],
            "prices": [bar["close"] for bar in bars], "numerical_agreement": False,
            "price_basis": "single_source_close",
            "snapshot_provenance_unverified": {
                "snapshot_sha256": hashlib.sha256(_canonical_json_bytes(snapshot)).hexdigest(),
                "upstream": dataset["provenance"]["upstream"],
                "interface": dataset["provenance"]["interface"],
                "retrieved_at": dataset["provenance"]["retrieved_at"],
                "evidence_as_of": dataset["evidence_as_of"], "adjustment": dataset["adjustment"],
                "source_content_verified": False, "historical_point_in_time_verified": False},
        }
    result = {"schema_version": "0.1", "data_kind": config["data_kind"],
              "symbols": plan["symbols"], "analysis_date": config["analysis_date"], "reports": reports}
    _canonical_json_bytes(result)
    return result


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args(argv)
    source, output = Path(args.input), Path(args.output)
    if output.is_symlink() or source.resolve() == output.resolve() or (output.exists() and os.path.samefile(source, output)):
        raise ValueError("output cannot overwrite an input or symbolic link")
    with source.open("rb") as stream:
        raw = stream.read(MAX_INPUT_BYTES + 1)
    if len(raw) > MAX_INPUT_BYTES:
        raise ValueError("snapshot input JSON too large")
    try:
        config = json.loads(raw, object_pairs_hook=_unique_object)
    except (ValueError, RecursionError, UnicodeError) as exc:
        raise ValueError("invalid snapshot JSON") from exc
    encoded = _canonical_json_bytes(build_snapshot_research_config(config)) + b"\n"
    output.parent.mkdir(parents=True, exist_ok=True)
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(mode="wb", dir=output.parent, delete=False) as stream:
            temporary = Path(stream.name)
            stream.write(encoded)
        os.replace(temporary, output)
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
