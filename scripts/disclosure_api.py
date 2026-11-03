"""Conservative HTTPS fetch for an official disclosure JSON endpoint.

The endpoint URL is caller supplied. This is a transport adapter, not an
assertion of data authenticity or a stable exchange API contract.
"""
import json
from urllib.parse import urlsplit
from urllib.request import Request, build_opener, HTTPRedirectHandler

if __package__:
    from .official_disclosures import OFFICIAL_HOSTS, adapt_official_disclosure
else:
    from official_disclosures import OFFICIAL_HOSTS, adapt_official_disclosure

MAX_RESPONSE_BYTES = 2_000_000
MAX_RECORDS = 500


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def validate_endpoint(url, *, source):
    if source not in OFFICIAL_HOSTS:
        raise ValueError("unsupported official disclosure source")
    if not isinstance(url, str):
        raise ValueError("endpoint must be a URL string")
    try:
        parsed = urlsplit(url)
        port = parsed.port
    except ValueError as exc:
        raise ValueError("invalid endpoint URL") from exc
    if (parsed.scheme != "https" or parsed.hostname not in OFFICIAL_HOSTS[source]
            or parsed.username or parsed.password or port not in (None, 443)
            or parsed.fragment):
        raise ValueError("endpoint must be an approved official HTTPS URL")
    return url


def fetch_official_disclosure_json(url, *, source, analysis_date, timeout=10,
                                   symbol=None):
    """Fetch an official-host JSON array, validate notices, return unverified metadata.

    Redirects are disabled, response size is bounded, and no API key is used.
    This function does not verify the publisher's historical availability.
    """
    validate_endpoint(url, source=source)
    if isinstance(timeout, bool) or not isinstance(timeout, (int, float)) or not 0 < timeout <= 30:
        raise ValueError('timeout must be between 0 and 30 seconds')
    request = Request(url, headers={"Accept": "application/json",
                                    "User-Agent": "stock-market-Agent/0.2"})
    with build_opener(NoRedirect()).open(request, timeout=timeout) as response:
        content_type = response.headers.get("Content-Type", "").split(";", 1)[0].strip().lower()
        if content_type not in ("application/json", "text/json"):
            raise ValueError("official endpoint did not return JSON content type")
        body = response.read(MAX_RESPONSE_BYTES + 1)
        if len(body) > MAX_RESPONSE_BYTES:
            raise ValueError("official endpoint response too large")
    try:
        records = json.loads(body.decode("utf-8"))
    except (UnicodeError, json.JSONDecodeError) as exc:
        raise ValueError("official endpoint returned invalid JSON") from exc
    if source == "cninfo" and symbol is not None:
        return normalize_cninfo_query_response(records, symbol=symbol,
                                               analysis_date=analysis_date)
    if not isinstance(records, list):
        raise ValueError("official endpoint must return a JSON list")
    if len(records) > MAX_RECORDS:
        raise ValueError("official endpoint returned too many records")
    return [adapt_official_disclosure(record, source=source,
                                      analysis_date=analysis_date)
            for record in records]


def normalize_cninfo_query_response(payload, *, symbol, analysis_date):
    """Convert a CNINFO-style announcements wrapper into unverified candidates.

    This is an offline schema adapter. The external endpoint contract and
    historical point-in-time availability are not independently verified.
    """
    if not isinstance(payload, dict) or not isinstance(payload.get("announcements"), list):
        raise ValueError("CNINFO response requires announcements list")
    if len(payload["announcements"]) > MAX_RECORDS:
        raise ValueError("CNINFO response contains too many announcements")
    if not isinstance(symbol, str) or not symbol.endswith((".SZ", ".SS")):
        raise ValueError("A-share symbol required")
    records = []
    for notice in payload["announcements"]:
        if not isinstance(notice, dict):
            raise ValueError("announcement must be an object")
        if notice.get("secCode") != symbol.split(".")[0]:
            raise ValueError("CNINFO announcement stock code mismatch")
        adjunct = notice.get("adjunctUrl")
        if not isinstance(adjunct, str) or not adjunct.startswith("finalpage/"):
            raise ValueError("unexpected CNINFO PDF path")
        if ("?" in adjunct or "#" in adjunct or "\\" in adjunct or
                any(part in ("", ".", "..") for part in adjunct.split("/")) or
                not adjunct.lower().endswith(".pdf")):
            raise ValueError("invalid CNINFO PDF path")
        milliseconds = notice.get("announcementTime")
        if isinstance(milliseconds, str) and milliseconds.isascii() and milliseconds.isdecimal():
            milliseconds = int(milliseconds)
        if type(milliseconds) is not int or not 0 <= milliseconds <= 253402300799999:
            raise ValueError("CNINFO announcementTime must be milliseconds")
        from datetime import datetime, timezone
        from zoneinfo import ZoneInfo
        timestamp = datetime.fromtimestamp(milliseconds / 1000, tz=timezone.utc)
        local = timestamp.astimezone(ZoneInfo("Asia/Shanghai"))
        records.append({
            "symbol": symbol,
            "title": notice.get("announcementTitle"),
            "url": "https://static.cninfo.com.cn/" + adjunct,
            "announcement_date": local.date().isoformat(),
            "published_at": local.isoformat(),
        })
    return [adapt_official_disclosure(record, source="cninfo",
                                      analysis_date=analysis_date)
            for record in records]


def fetch_disclosure_snapshot(url, *, source, analysis_date, symbol=None, timeout=10):
    """Return unverified notices with a UTC retrieval timestamp and endpoint.

    The timestamp documents retrieval only, never historical availability.
    """
    from datetime import datetime, timezone
    notices = fetch_official_disclosure_json(
        url, source=source, analysis_date=analysis_date,
        symbol=symbol, timeout=timeout)
    return {
        "schema_version": "0.1",
        "source": source,
        "endpoint": validate_endpoint(url, source=source),
        "analysis_date": analysis_date,
        "retrieved_at": datetime.now(timezone.utc).isoformat(),
        "records": notices,
        "source_content_verified": False,
        "historical_point_in_time_verified": False,
        "limitations": [
            "Retrieval time is not publication time or historical availability proof.",
            "Endpoint host allowlisting does not authenticate announcement content.",
        ],
    }


def save_disclosure_snapshot(directory, snapshot):
    """Write a bounded JSON snapshot atomically, without secrets or model calls."""
    import os
    import tempfile
    from pathlib import Path
    directory = Path(directory)
    if not isinstance(snapshot, dict) or snapshot.get("source_content_verified") is not False:
        raise ValueError("snapshot must explicitly remain unverified")
    if snapshot.get("historical_point_in_time_verified") is not False:
        raise ValueError("snapshot must not claim historical verification")
    directory.mkdir(parents=True, exist_ok=True)
    target = directory / "disclosure_api_snapshot.json"
    encoded = (json.dumps(snapshot, ensure_ascii=False, indent=2) + "\n").encode("utf-8")
    if len(encoded) > MAX_RESPONSE_BYTES * 2:
        raise ValueError("snapshot too large")
    tmp_path = None
    try:
        with tempfile.NamedTemporaryFile(mode="wb", dir=directory, prefix=".disclosure-",
                                         suffix=".tmp", delete=False) as stream:
            tmp_path = stream.name
            stream.write(encoded)
        os.replace(tmp_path, target)
    finally:
        if tmp_path is not None and os.path.exists(tmp_path):
            os.unlink(tmp_path)
    return target


def collect_disclosure_candidates(url, *, source, analysis_date, symbol,
                                  output_dir, timeout=10):
    """Fetch, screen and persist unverified records without LLM or trading."""
    if __package__:
        from .disclosure_candidates import screen_disclosures, save_disclosure_candidates
    else:
        from disclosure_candidates import screen_disclosures, save_disclosure_candidates
    snapshot = fetch_disclosure_snapshot(
        url, source=source, analysis_date=analysis_date,
        symbol=symbol, timeout=timeout)
    candidates = screen_disclosures(
        snapshot["records"], analysis_date=analysis_date, symbol=symbol)
    # Validate the complete candidate set before writing either artifact.
    snapshot_path = save_disclosure_snapshot(output_dir, snapshot)
    candidates_path = save_disclosure_candidates(output_dir, candidates)
    return {"snapshot_path": snapshot_path, "candidates_path": candidates_path,
            "candidate_count": len(candidates["candidates"])}


def main():
    """Opt-in, read-only CLI for a caller-supplied official JSON endpoint."""
    import argparse
    parser = argparse.ArgumentParser(
        description="Fetch and screen unverified official-host disclosure metadata")
    parser.add_argument("--endpoint", required=True)
    parser.add_argument("--source", choices=tuple(OFFICIAL_HOSTS), required=True)
    parser.add_argument("--analysis-date", required=True)
    parser.add_argument("--symbol", required=True)
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--timeout", type=float, default=10)
    args = parser.parse_args()
    result = collect_disclosure_candidates(
        args.endpoint, source=args.source, analysis_date=args.analysis_date,
        symbol=args.symbol, output_dir=args.output_dir, timeout=args.timeout)
    print(f"Unverified candidates: {result['candidate_count']}")
    print(result["snapshot_path"])
    print(result["candidates_path"])


if __name__ == "__main__":
    main()
