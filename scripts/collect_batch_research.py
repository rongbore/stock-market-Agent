"""Explicit opt-in single-upstream AKShare collection to an offline batch ZIP."""
import argparse
from datetime import datetime, timezone
import hashlib
from io import BytesIO
import os
from pathlib import Path
import tempfile
from zipfile import ZIP_STORED, ZipFile, ZipInfo

from scripts.akshare_provider import _dates, _symbol, fetch_a_share_daily
from scripts.akshare_sina_provider import fetch_sina_daily
from scripts.backtest_data_contract import build_backtest_dataset
from scripts.batch_research_package import build_batch_research_package
from scripts.calendar_acceptance_cli import _load
from scripts.market_calendar_coverage import validate_calendar
from scripts.market_date_window import resolve_market_window
from scripts.offline_batch_research_runner import _canonical_json_bytes

MAX_ITEMS = 5


def _sha(value):
    return hashlib.sha256(_canonical_json_bytes(value)).hexdigest()


def validate_collection_request(request, *, now=None):
    """Validate every item before any network request or optional dependency load."""
    _canonical_json_bytes(request)
    if type(request) is not dict or set(request) != {"schema_version", "upstream", "start_date", "end_date", "items"}:
        raise ValueError("collection request requires exact fields")
    if request["schema_version"] != "0.1" or type(request["upstream"]) is not str or request["upstream"] not in ("eastmoney", "sina"):
        raise ValueError("select exactly one supported upstream")
    _dates(request["start_date"], request["end_date"])
    resolve_market_window(request["start_date"], request["end_date"], now=now)
    items = request["items"]
    if type(items) is not list or not 1 <= len(items) <= MAX_ITEMS:
        raise ValueError("collection supports 1 to 5 explicit items")
    seen = set()
    for item in items:
        if type(item) is not dict or set(item) != {"symbol", "calendar"}:
            raise ValueError("each item requires a symbol and explicit calendar")
        _symbol(item["symbol"])
        if item["symbol"] in seen:
            raise ValueError("duplicate collection symbol")
        seen.add(item["symbol"])
        validate_calendar(item["calendar"], item["symbol"], request["start_date"], request["end_date"])
    return request


def build_collected_batch_package(request, *, allow_network=False, fetcher=None, now=None):
    """Fetch each selected symbol once, isolate failures and recompute raw research."""
    if allow_network is not True:
        raise ValueError("explicit network opt-in required")
    validate_collection_request(request, now=now)
    selected = fetcher or (fetch_a_share_daily if request["upstream"] == "eastmoney" else fetch_sina_daily)
    collected, jobs, snapshots = [], [], {}
    for item in sorted(request["items"], key=lambda item: item["symbol"]):
        symbol = item["symbol"]
        entry = {"symbol": symbol, "status": "FAILED_COLLECTION", "reason": "collection_failed",
                 "calendar_sha256": _sha(item["calendar"]), "source_content_verified": False,
                 "historical_point_in_time_verified": False, "exchange_calendar_verified": False}
        snapshot = None
        try:
            fetched = selected(symbol, request["start_date"], request["end_date"], adjust="")
        except Exception:
            fetched = None
        cutoff = (now if now is not None else datetime.now(timezone.utc)).isoformat()
        if fetched is not None:
            entry.update(status="FAILED_SNAPSHOT_VALIDATION", reason="snapshot_validation_failed")
            try:
                _canonical_json_bytes(fetched)
                if (type(fetched) is not dict or fetched.get("symbol") != symbol
                        or fetched.get("upstream") != request["upstream"]
                        or fetched.get("start_date") != request["start_date"]
                        or fetched.get("end_date") != request["end_date"]):
                    raise ValueError("provider identity/window mismatch")
                dataset = build_backtest_dataset(fetched, evidence_as_of=cutoff, expected_adjustment="unadjusted")
                snapshot = fetched
                snapshots["collected/" + symbol + ".snapshot.json"] = _canonical_json_bytes(snapshot) + b"\n"
                entry.update(status="COLLECTED_UNVERIFIED", reason=None, snapshot_sha256=_sha(snapshot),
                             retrieved_at=dataset["provenance"]["retrieved_at"],
                             interface=dataset["provenance"]["interface"], record_count=len(dataset["bars"]))
            except Exception:
                snapshot = None
        entry["evidence_as_of"] = cutoff
        collected.append(entry)
        jobs.append({"symbol": symbol, "config": {"schema_version": "0.1", "data_kind": "UNVERIFIED_LOCAL",
                     "evidence_as_of": cutoff, "expected_adjustment": "unadjusted",
                     "snapshot": snapshot, "calendar": item["calendar"]}})
    base_bytes, manifest = build_batch_research_package({"schema_version": "0.1", "items": jobs})
    metadata = {"schema_version": "0.1", "request": request, "request_sha256": _sha(request),
                "upstream": request["upstream"], "adjustment": "unadjusted", "items": collected,
                "status": manifest["status"], "source_content_verified": False,
                "historical_point_in_time_verified": False, "exchange_calendar_verified": False,
                "limitations": ["Single explicitly selected upstream; no cross-source agreement is asserted.",
                                "Only structure-validated normalized snapshots are retained, not raw HTTP responses.",
                                "Provider timeout/retry behavior is inherited; no transport deadline is added."]}
    with ZipFile(BytesIO(base_bytes)) as archive:
        files = {name: archive.read(name) for name in archive.namelist() if name != "manifest.json"}
    files.update(snapshots)
    files["collection.json"] = _canonical_json_bytes(metadata) + b"\n"
    manifest = {**manifest, "collection_request_sha256": _sha(request),
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
    parser.add_argument("--input", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--allow-network", required=True, action="store_true")
    args = parser.parse_args(argv)
    request = _load(args.input)
    validate_collection_request(request)
    output = Path(args.output)
    if output.exists() or output.is_symlink():
        raise FileExistsError("collection ZIP output must be a new file")
    output.parent.mkdir(parents=True, exist_ok=True)
    temporary = None
    try:
        # Verify destination access before fetching any provider data.
        with tempfile.NamedTemporaryFile(mode="wb", dir=output.parent, delete=False) as stream:
            temporary = Path(stream.name)
        encoded, manifest = build_collected_batch_package(request, allow_network=args.allow_network)
        with temporary.open("wb") as stream:
            stream.write(encoded)
        os.link(temporary, output)
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)
    return 0 if manifest["status"] == "ALL_RESEARCH_GENERATED_UNVERIFIED" else 2


if __name__ == "__main__":
    raise SystemExit(main())
