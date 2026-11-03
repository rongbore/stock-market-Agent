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
    records = json.loads(body.decode("utf-8"))
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
