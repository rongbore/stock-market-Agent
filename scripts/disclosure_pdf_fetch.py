"""Opt-in bounded download and fingerprinting of CNINFO PDF originals.

The artifact records bytes retrieved from an allowlisted host. It does not
prove the document's authenticity, contents, or historical availability.
"""
import hashlib
import os
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import unquote, urlsplit
from urllib.request import HTTPRedirectHandler, Request, build_opener

MAX_PDF_BYTES = 20 * 1024 * 1024
CNINFO_PDF_HOST = "static.cninfo.com.cn"


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def validate_cninfo_pdf_url(url):
    """Accept only canonical HTTPS CNINFO finalpage PDF URLs."""
    if not isinstance(url, str) or len(url) > 2048:
        raise ValueError("invalid CNINFO PDF URL")
    try:
        parsed = urlsplit(url)
        port = parsed.port
    except ValueError as exc:
        raise ValueError("invalid CNINFO PDF URL") from exc
    decoded_path = unquote(parsed.path)
    if (parsed.scheme != "https" or parsed.hostname != CNINFO_PDF_HOST
            or parsed.username or parsed.password or port not in (None, 443)
            or parsed.query or parsed.fragment or "%" in parsed.path
            or "%" in decoded_path
            or "\\" in decoded_path or any(ord(c) < 32 for c in decoded_path)
            or not decoded_path.startswith("/finalpage/")
            or not decoded_path.lower().endswith(".pdf")
            or any(part in ("", ".", "..")
                   for part in decoded_path[1:].split("/"))):
        raise ValueError("URL must be a canonical CNINFO HTTPS finalpage PDF")
    return url


def fetch_cninfo_pdf(record, output_dir, *, timeout=10):
    """Download one bounded PDF and persist a hash manifest with conservative flags."""
    if not isinstance(record, dict):
        raise ValueError("disclosure record required")
    url = validate_cninfo_pdf_url(record.get("url"))
    symbol = record.get("symbol")
    announcement_date = record.get("announcement_date")
    if (not isinstance(symbol, str) or len(symbol) != 9
            or symbol[6:] not in (".SZ", ".SS")
            or not symbol[:6].isascii() or not symbol[:6].isdigit()
            or not isinstance(announcement_date, str)):
        raise ValueError("valid A-share symbol and announcement date required")
    try:
        if datetime.strptime(announcement_date, "%Y-%m-%d").date().isoformat() != announcement_date:
            raise ValueError
    except ValueError as exc:
        raise ValueError("announcement_date must be YYYY-MM-DD") from exc
    if isinstance(timeout, bool) or not isinstance(timeout, (int, float)) or not 0 < timeout <= 30:
        raise ValueError("timeout must be between 0 and 30 seconds")

    request = Request(url, headers={
        "Accept": "application/pdf",
        "User-Agent": "stock-market-Agent/0.2",
    })
    with build_opener(NoRedirect()).open(request, timeout=timeout) as response:
        content_type = response.headers.get("Content-Type", "").split(";", 1)[0].strip().lower()
        if content_type != "application/pdf":
            raise ValueError("CNINFO document did not return PDF content type")
        body = response.read(MAX_PDF_BYTES + 1)
    if len(body) > MAX_PDF_BYTES:
        raise ValueError("CNINFO PDF exceeds size limit")
    if len(body) < 12 or not body.startswith(b"%PDF-") or b"%%EOF" not in body[-2048:]:
        raise ValueError("CNINFO response is not a complete PDF")

    digest = hashlib.sha256(body).hexdigest()
    directory = Path(output_dir)
    directory.mkdir(parents=True, exist_ok=True)
    url_id = hashlib.sha256(url.encode("utf-8")).hexdigest()[:16]
    filename = f"{symbol}_{announcement_date}_{url_id}.pdf"
    target = directory / filename
    if target.is_symlink() or (target.exists() and not target.is_file()):
        raise ValueError("refusing non-regular PDF artifact path")
    if target.exists() and hashlib.sha256(target.read_bytes()).hexdigest() != digest:
        raise ValueError("refusing to replace a different existing PDF artifact")
    if not target.exists():
        tmp_path = None
        try:
            with tempfile.NamedTemporaryFile(mode="wb", dir=directory,
                                             prefix=".cninfo-pdf-", suffix=".tmp",
                                             delete=False) as stream:
                tmp_path = stream.name
                stream.write(body)
                stream.flush()
                os.fsync(stream.fileno())
            os.replace(tmp_path, target)
        finally:
            if tmp_path is not None and os.path.exists(tmp_path):
                os.unlink(tmp_path)
    return {
        "source_url": url,
        "relative_path": filename,
        "retrieved_at": datetime.now(timezone.utc).isoformat(),
        "sha256": digest,
        "size_bytes": len(body),
        "pdf_header_present": True,
        "pdf_eof_marker_present": True,
        "official_origin_verified": False,
        "source_content_verified": False,
        "historical_point_in_time_verified": False,
        "note": "Fingerprint of retrieved bytes only; authenticity, contents, and historical availability remain unverified.",
    }
