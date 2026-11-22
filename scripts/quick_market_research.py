"""Opt-in vendor-calendar preparation and single-source collection to research ZIP."""
import argparse
import hashlib
from io import BytesIO
import os
from pathlib import Path
import tempfile
from zipfile import ZIP_STORED, ZipFile, ZipInfo

from scripts.akshare_provider import _symbol
from scripts.collect_batch_research import MAX_ITEMS, build_collected_batch_package, validate_collection_request
from scripts.market_calendar_provider import fetch_sina_calendar
from scripts.market_date_window import resolve_market_window
from scripts.offline_batch_research_runner import _canonical_json_bytes


def build_quick_research_package(symbols, upstream, *, start_date=None, end_date=None,
                                 allow_network=False, calendar_fetcher=None, price_fetcher=None, now=None):
    """Use separately fetched vendor sessions, not sessions inferred from prices."""
    if allow_network is not True:
        raise ValueError("explicit network opt-in required")
    if type(symbols) is not list or not 1 <= len(symbols) <= MAX_ITEMS:
        raise ValueError("select 1 to 5 explicit A-share symbols")
    for symbol in symbols:
        _symbol(symbol)
    if len(set(symbols)) != len(symbols) or upstream not in ("sina", "eastmoney"):
        raise ValueError("unique symbols and an explicit supported upstream required")
    window = resolve_market_window(start_date, end_date, now=now)
    calendar_fetcher = calendar_fetcher or fetch_sina_calendar
    sessions, metadata = calendar_fetcher(window["start_date"], window["end_date"], now=now)
    if type(sessions) is not list or not sessions or type(metadata) is not dict:
        raise ValueError("vendor calendar must provide sessions and metadata")
    _canonical_json_bytes(metadata)
    source = "Unverified AKShare Sina sessions; interface=" + metadata["interface"] + "; full_dates_sha256=" + metadata["full_date_list_sha256"]
    request = {"schema_version": "0.1", "upstream": upstream,
               "start_date": window["start_date"], "end_date": window["end_date"],
               "items": [{"symbol": symbol, "calendar": {"schema_version": "0.1", "exchange": symbol[-2:],
                          "start_date": window["start_date"], "end_date": window["end_date"],
                          "source": source, "sessions": list(sessions)}} for symbol in sorted(symbols)]}
    validate_collection_request(request, now=now)
    encoded, manifest = build_collected_batch_package(request, allow_network=True, fetcher=price_fetcher, now=now)
    with ZipFile(BytesIO(encoded)) as archive:
        files = {name: archive.read(name) for name in archive.namelist() if name != "manifest.json"}
    calendar_record = {"schema_version": "0.1", "vendor_metadata_supplied_unverified": metadata,
                       "window": window, "sessions": sessions, "symbols": sorted(symbols),
                       "exchange_calendar_verified": False, "independent_source_verified": False,
                       "limitations": ["Vendor sessions are reused for SZ/SS as an unverified caller assumption.",
                                       "Calendar retrieval is separate from prices; source independence is not established.",
                                       "No suspension, official publication or historical availability certification."]}
    files["calendar-source.json"] = _canonical_json_bytes(calendar_record) + b"\n"
    manifest = {**manifest, "calendar_source_file": "calendar-source.json",
                "files": [{"path": name, "size_bytes": len(data), "sha256": hashlib.sha256(data).hexdigest()}
                          for name, data in sorted(files.items())]}
    files["manifest.json"] = _canonical_json_bytes(manifest) + b"\n"
    stream = BytesIO()
    with ZipFile(stream, "w", compression=ZIP_STORED) as archive:
        for name, data in sorted(files.items()):
            info = ZipInfo(name, date_time=(1980, 1, 1, 0, 0, 0))
            info.compress_type = ZIP_STORED
            info.create_system = 3
            info.external_attr = 0o100644 << 16
            archive.writestr(info, data)
    return stream.getvalue(), manifest


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--symbols", nargs="+", required=True)
    parser.add_argument("--upstream", choices=("sina", "eastmoney"), required=True)
    parser.add_argument("--start-date")
    parser.add_argument("--end-date")
    parser.add_argument("--allow-network", action="store_true", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args(argv)
    output = Path(args.output)
    if output.exists() or output.is_symlink():
        raise FileExistsError("quick research output must be a new file")
    output.parent.mkdir(parents=True, exist_ok=True)
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(mode="wb", dir=output.parent, delete=False) as stream:
            temporary = Path(stream.name)
        encoded, manifest = build_quick_research_package(args.symbols, args.upstream,
            start_date=args.start_date, end_date=args.end_date, allow_network=args.allow_network)
        temporary.write_bytes(encoded)
        os.link(temporary, output)
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)
    return 0 if manifest["status"] == "ALL_RESEARCH_GENERATED_UNVERIFIED" else 2


if __name__ == "__main__":
    raise SystemExit(main())
