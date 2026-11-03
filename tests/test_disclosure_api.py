import io
import json
import unittest
from unittest.mock import patch

from scripts.disclosure_api import NoRedirect, fetch_official_disclosure_json, normalize_cninfo_query_response, validate_endpoint


class FakeResponse:
    def __init__(self, payload, content_type="application/json"):
        self.payload = payload
        self.headers = {"Content-Type": content_type}

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def read(self, limit):
        return self.payload[:limit]


class FakeOpener:
    def __init__(self, response):
        self.response = response

    def open(self, request, timeout):
        return self.response


class OfficialDisclosureAPITests(unittest.TestCase):
    def setUp(self):
        self.endpoint = "https://www.cninfo.com.cn/api/disclosure.json"
        self.record = {
            "symbol": "000776.SZ",
            "title": "SYNTHETIC NOTICE",
            "url": "https://static.cninfo.com.cn/finalpage/test.pdf",
            "announcement_date": "2026-10-29",
        }

    def fetch(self, payload, content_type="application/json"):
        with patch("scripts.disclosure_api.build_opener",
                   return_value=FakeOpener(FakeResponse(payload, content_type))):
            return fetch_official_disclosure_json(
                self.endpoint, source="cninfo", analysis_date="2026-10-30")

    def test_cninfo_wrapper_mapping(self):
        from datetime import datetime
        from zoneinfo import ZoneInfo
        stamp = int(datetime(2026, 10, 29, 16, 0,
                             tzinfo=ZoneInfo("Asia/Shanghai")).timestamp() * 1000)
        payload = {"announcements": [{
            "secCode": "000776", "announcementTitle": "SYNTHETIC NOTICE",
            "adjunctUrl": "finalpage/2026-10-29/sample.PDF",
            "announcementTime": stamp,
        }]}
        result = normalize_cninfo_query_response(
            payload, symbol="000776.SZ", analysis_date="2026-10-30")
        self.assertEqual(result[0]["announcement_date"], "2026-10-29")
        self.assertFalse(result[0]["source_content_verified"])
        self.assertFalse(result[0]["publication_time_verified"])

    def test_cninfo_wrapper_rejects_wrong_symbol_and_bad_path(self):
        payload = {"announcements": [{
            "secCode": "000777", "announcementTitle": "SYNTHETIC",
            "adjunctUrl": "finalpage/test.PDF", "announcementTime": 1790000000000,
        }]}
        with self.assertRaises(ValueError):
            normalize_cninfo_query_response(
                payload, symbol="000776.SZ", analysis_date="2026-10-30")
        payload["announcements"][0]["secCode"] = "000776"
        payload["announcements"][0]["adjunctUrl"] = "finalpage/../secret"
        with self.assertRaises(ValueError):
            normalize_cninfo_query_response(
                payload, symbol="000776.SZ", analysis_date="2026-10-30")

    def test_valid_json_metadata_stays_unverified(self):
        records = self.fetch(json.dumps([self.record]).encode())
        self.assertEqual(len(records), 1)
        self.assertFalse(records[0]["source_content_verified"])
        self.assertFalse(records[0]["publication_time_verified"])

    def test_redirects_are_disabled(self):
        handler = NoRedirect()
        self.assertIsNone(handler.redirect_request(
            None, None, 302, 'Found', {}, 'https://evil.example/'))

    def test_credentials_and_fragment_rejected(self):
        for url in ('https://user:pass@www.cninfo.com.cn/api',
                    'https://www.cninfo.com.cn/api#fragment'):
            with self.subTest(url=url), self.assertRaises(ValueError):
                validate_endpoint(url, source='cninfo')

    def test_official_host_required(self):
        for url in ("https://www.cninfo.com.cn.evil.example/api",
                    "http://www.cninfo.com.cn/api",
                    "https://www.cninfo.com.cn:444/api"):
            with self.subTest(url=url), self.assertRaises(ValueError):
                validate_endpoint(url, source="cninfo")

    def test_non_json_response_rejected(self):
        with self.assertRaisesRegex(ValueError, "content type"):
            self.fetch(b"<html>error</html>", "text/html")

    def test_oversized_response_rejected(self):
        with self.assertRaisesRegex(ValueError, "too large"):
            self.fetch(b" " * 2_000_001)

    def test_unexpected_json_shape_rejected(self):
        with self.assertRaisesRegex(ValueError, "JSON list"):
            self.fetch(b'{"records": []}')

    def test_future_announcement_rejected(self):
        self.record["announcement_date"] = "2026-11-01"
        with self.assertRaises(ValueError):
            self.fetch(json.dumps([self.record]).encode())


if __name__ == "__main__":
    unittest.main()
