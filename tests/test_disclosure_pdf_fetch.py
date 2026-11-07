import hashlib
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from scripts.disclosure_pdf_fetch import (
    MAX_PDF_BYTES,
    NoRedirect,
    fetch_cninfo_pdf,
    validate_cninfo_pdf_url,
)


class FakeResponse:
    def __init__(self, body, content_type="application/pdf"):
        self.body = body
        self.headers = {"Content-Type": content_type}

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def read(self, limit):
        return self.body[:limit]


class FakeOpener:
    def __init__(self, response):
        self.response = response
        self.calls = []

    def open(self, request, timeout):
        self.calls.append((request, timeout))
        return self.response


class DisclosurePdfFetchTests(unittest.TestCase):
    url = "https://static.cninfo.com.cn/finalpage/2026-10-29/report.pdf"
    record = {
        "symbol": "000776.SZ",
        "announcement_date": "2026-10-29",
        "url": url,
    }
    pdf = b"%PDF-1.7\nminimal synthetic PDF\n%%EOF\n"

    def test_valid_pdf_is_saved_with_sha256_and_unverified_flags(self):
        opener = FakeOpener(FakeResponse(self.pdf))
        with tempfile.TemporaryDirectory() as tmp, patch(
                "scripts.disclosure_pdf_fetch.build_opener", return_value=opener):
            artifact = fetch_cninfo_pdf(self.record, tmp)
            saved = Path(tmp) / artifact["relative_path"]
            self.assertEqual(saved.read_bytes(), self.pdf)
            self.assertEqual(artifact["sha256"], hashlib.sha256(self.pdf).hexdigest())
            self.assertEqual(artifact["size_bytes"], len(self.pdf))
            self.assertFalse(artifact["official_origin_verified"])
            self.assertFalse(artifact["source_content_verified"])
            self.assertFalse(artifact["historical_point_in_time_verified"])
            self.assertEqual(opener.calls[0][1], 10)

    def test_same_bytes_are_idempotent_and_different_bytes_do_not_overwrite(self):
        with tempfile.TemporaryDirectory() as tmp:
            with patch("scripts.disclosure_pdf_fetch.build_opener",
                       return_value=FakeOpener(FakeResponse(self.pdf))):
                first = fetch_cninfo_pdf(self.record, tmp)
                second = fetch_cninfo_pdf(self.record, tmp)
            self.assertEqual(first["relative_path"], second["relative_path"])
            other = self.pdf + b"changed"
            with patch("scripts.disclosure_pdf_fetch.build_opener",
                       return_value=FakeOpener(FakeResponse(other))):
                with self.assertRaisesRegex(ValueError, "different existing"):
                    fetch_cninfo_pdf(self.record, tmp)

    def test_only_canonical_cninfo_finalpage_pdf_urls_are_accepted(self):
        self.assertEqual(validate_cninfo_pdf_url(self.url), self.url)
        for url in (
            "https://static.cninfo.com.cn.evil.example/finalpage/a.pdf",
            "https://user@static.cninfo.com.cn/finalpage/a.pdf",
            "http://static.cninfo.com.cn/finalpage/a.pdf",
            "https://static.cninfo.com.cn/finalpage/../secret.pdf",
            "https://static.cninfo.com.cn/finalpage/a%2epdf",
            "https://static.cninfo.com.cn/finalpage/a.pdf?redirect=https://evil.example",
            "https://static.cninfo.com.cn/other/a.pdf",
        ):
            with self.subTest(url=url), self.assertRaises(ValueError):
                validate_cninfo_pdf_url(url)

    def test_bad_content_type_pdf_header_or_eof_is_rejected(self):
        for body, content_type in (
            (self.pdf, "text/html"),
            (b"<html>%%EOF</html>", "application/pdf"),
            (b"%PDF-1.7\ntruncated body", "application/pdf"),
        ):
            with self.subTest(content_type=content_type, body=body), \
                    tempfile.TemporaryDirectory() as tmp, \
                    patch("scripts.disclosure_pdf_fetch.build_opener",
                          return_value=FakeOpener(FakeResponse(body, content_type))):
                with self.assertRaises(ValueError):
                    fetch_cninfo_pdf(self.record, tmp)
                self.assertEqual(list(Path(tmp).iterdir()), [])

    def test_oversize_pdf_and_invalid_timeout_fail_closed(self):
        with tempfile.TemporaryDirectory() as tmp, \
                patch("scripts.disclosure_pdf_fetch.MAX_PDF_BYTES", 20), \
                patch("scripts.disclosure_pdf_fetch.build_opener",
                      return_value=FakeOpener(FakeResponse(self.pdf))):
            with self.assertRaisesRegex(ValueError, "size limit"):
                fetch_cninfo_pdf(self.record, tmp)
        self.assertEqual(MAX_PDF_BYTES, 20 * 1024 * 1024)
        for timeout in (0, 31, True, "10"):
            with self.subTest(timeout=timeout), tempfile.TemporaryDirectory() as tmp, \
                    self.assertRaisesRegex(ValueError, "timeout"):
                fetch_cninfo_pdf(self.record, tmp, timeout=timeout)

    def test_redirect_handler_never_follows_to_another_host(self):
        handler = NoRedirect()
        self.assertIsNone(handler.redirect_request(
            None, None, 302, "Found", {}, "https://evil.example/a.pdf"))

    def test_invalid_record_is_rejected_before_network_or_file_creation(self):
        opener = FakeOpener(FakeResponse(self.pdf))
        with tempfile.TemporaryDirectory() as tmp, patch(
                "scripts.disclosure_pdf_fetch.build_opener", return_value=opener):
            with self.assertRaisesRegex(ValueError, "symbol"):
                fetch_cninfo_pdf(dict(self.record, symbol="000776.XY"), tmp)
            self.assertEqual(opener.calls, [])
            self.assertEqual(list(Path(tmp).iterdir()), [])


if __name__ == "__main__":
    unittest.main()
