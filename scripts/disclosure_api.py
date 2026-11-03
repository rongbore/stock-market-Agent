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


def fetch_official_disclosure_json(url, *, source, analysis_date, timeout=10):
    """Fetch an official-host JSON array, validate notices, return unverified metadata.

    Redirects are disabled, response size is bounded, and no API key is used.
    This function does not verify the publisher's historical availability.
    """
    validate_endpoint(url, source=source)
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
    if not isinstance(records, list):
        raise ValueError("official endpoint must return a JSON list")
    return [adapt_official_disclosure(record, source=source,
                                      analysis_date=analysis_date)
            for record in records]
