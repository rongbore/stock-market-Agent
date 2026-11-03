import io
import json
import unittest
from unittest.mock import patch

from scripts.disclosure_api import NoRedirect, collect_disclosure_candidates, fetch_disclosure_snapshot, fetch_official_disclosure_json, normalize_cninfo_query_response, save_disclosure_snapshot, validate_endpoint


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

    def test_fetch_cninfo_wrapped_json(self):
        from datetime import datetime
        from zoneinfo import ZoneInfo
        stamp = int(datetime(2026, 10, 29, 16, 0,
                             tzinfo=ZoneInfo("Asia/Shanghai")).timestamp() * 1000)
        payload = json.dumps({"announcements": [{
            "secCode": "000776", "announcementTitle": "SYNTHETIC NOTICE",
            "adjunctUrl": "finalpage/2026-10-29/sample.PDF",
            "announcementTime": stamp,
        }]}).encode()
        with patch("scripts.disclosure_api.build_opener",
                   return_value=FakeOpener(FakeResponse(payload))):
            result = fetch_official_disclosure_json(
                self.endpoint, source="cninfo", analysis_date="2026-10-30",
                symbol="000776.SZ")
        self.assertEqual(result[0]["symbol"], "000776.SZ")
        self.assertFalse(result[0]["source_content_verified"])

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
        payload["announcements"][0]["announcementTime"] = str(stamp)
        self.assertEqual(normalize_cninfo_query_response(
            payload, symbol="000776.SZ", analysis_date="2026-10-30")[0]["announcement_date"], "2026-10-29")

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

    def test_cninfo_rejects_invalid_timestamp_and_non_pdf(self):
        notice = {"secCode": "000776", "announcementTitle": "SYNTHETIC",
                  "adjunctUrl": "finalpage/sample.PDF", "announcementTime": "not-a-timestamp"}
        with self.assertRaises(ValueError):
            normalize_cninfo_query_response({"announcements": [notice]},
                                            symbol="000776.SZ", analysis_date="2026-10-30")
        notice["announcementTime"] = 1790000000000
        notice["adjunctUrl"] = "finalpage/sample.html"
        with self.assertRaises(ValueError):
            normalize_cninfo_query_response({"announcements": [notice]},
                                            symbol="000776.SZ", analysis_date="2026-10-30")

    def test_collect_invalid_candidate_leaves_no_artifacts(self):
        import tempfile
        from pathlib import Path
        invalid = dict(self.record, provider="CNINFO", symbol="000777.SZ")
        with tempfile.TemporaryDirectory() as tmp:
            with patch("scripts.disclosure_api.fetch_disclosure_snapshot",
                       return_value={
                           "source": "cninfo", "analysis_date": "2026-10-30",
                           "records": [invalid], "source_content_verified": False,
                           "historical_point_in_time_verified": False,
                       }):
                with self.assertRaises(ValueError):
                    collect_disclosure_candidates(
                        self.endpoint, source="cninfo", analysis_date="2026-10-30",
                        symbol="000776.SZ", output_dir=tmp)
            self.assertEqual(list(Path(tmp).iterdir()), [])

    def test_collect_screens_and_saves_both_artifacts(self):
        import tempfile
        from pathlib import Path
        from datetime import datetime, timezone
        notice = dict(self.record, provider="CNINFO")
        notice["published_at"] = "2026-10-29T16:00:00+08:00"
        with tempfile.TemporaryDirectory() as tmp:
            with patch("scripts.disclosure_api.fetch_disclosure_snapshot",
                       return_value={
                           "source": "cninfo", "endpoint": self.endpoint,
                           "analysis_date": "2026-10-30",
                           "retrieved_at": datetime.now(timezone.utc).isoformat(),
                           "records": [notice],
                           "source_content_verified": False,
                           "historical_point_in_time_verified": False,
                       }):
                result = collect_disclosure_candidates(
                    self.endpoint, source="cninfo", analysis_date="2026-10-30",
                    symbol="000776.SZ", output_dir=tmp)
            self.assertEqual(result["candidate_count"], 1)
            self.assertTrue(result["snapshot_path"].is_file())
            self.assertTrue(result["candidates_path"].is_file())
            candidates = json.loads(result["candidates_path"].read_text())
            self.assertFalse(candidates["source_content_verified"])

    def test_save_snapshot_and_reject_false_verification(self):
        import tempfile
        from pathlib import Path
        with tempfile.TemporaryDirectory() as tmp:
            snapshot = {"source_content_verified": False,
                        "historical_point_in_time_verified": False,
                        "records": [{"symbol": "000776.SZ"}]}
            path = save_disclosure_snapshot(Path(tmp), snapshot)
            self.assertEqual(json.loads(path.read_text(encoding="utf-8")), snapshot)
            self.assertFalse(list(Path(tmp).glob("*.tmp")))
            snapshot["source_content_verified"] = True
            with self.assertRaises(ValueError):
                save_disclosure_snapshot(Path(tmp), snapshot)

    def test_snapshot_records_retrieval_provenance_not_verification(self):
        with patch("scripts.disclosure_api.fetch_official_disclosure_json",
                   return_value=[{"symbol": "000776.SZ"}]):
            result = fetch_disclosure_snapshot(
                self.endpoint, source="cninfo", analysis_date="2026-10-30",
                symbol="000776.SZ")
        from datetime import datetime
        self.assertIsNotNone(datetime.fromisoformat(result["retrieved_at"]).tzinfo)
        self.assertEqual(result["endpoint"], self.endpoint)
        self.assertEqual(result["records"][0]["symbol"], "000776.SZ")
        self.assertFalse(result["source_content_verified"])
        self.assertFalse(result["historical_point_in_time_verified"])

    def test_timeout_validation(self):
        for timeout in (0, -1, 31, True, "10"):
            with self.subTest(timeout=timeout), self.assertRaisesRegex(ValueError, "timeout"):
                fetch_official_disclosure_json(
                    self.endpoint, source="cninfo",
                    analysis_date="2026-10-30", timeout=timeout)

    def test_record_count_limit(self):
        with self.assertRaisesRegex(ValueError, "too many records"):
            self.fetch(json.dumps([self.record] * 501).encode())
        with self.assertRaisesRegex(ValueError, "too many announcements"):
            normalize_cninfo_query_response(
                {"announcements": [{}] * 501},
                symbol="000776.SZ", analysis_date="2026-10-30")

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

    def test_endpoint_rejects_query_secrets_and_control_characters(self):
        for url in ("https://www.cninfo.com.cn/api?token=secret",
                    "https://www.cninfo.com.cn/api?stock=000776",
                    "https://www.cninfo.com.cn/api\nX-Test: injected"):
            with self.subTest(url=url), self.assertRaises(ValueError):
                validate_endpoint(url, source="cninfo")

    def test_cli_invalid_inputs_fail_before_network(self):
        import subprocess
        import sys
        base = [sys.executable, "scripts/disclosure_api.py",
                "--endpoint", "https://www.cninfo.com.cn/example",
                "--source", "cninfo", "--analysis-date", "2026-10-30",
                "--symbol", "000776.SZ", "--output-dir", "unused"]
        for flag, bad in (("--analysis-date", "2026-02-30"),
                          ("--symbol", "000776.XY"),
                          ("--endpoint", "http://www.cninfo.com.cn/example")):
            with self.subTest(flag=flag):
                args = base[:]
                args[args.index(flag) + 1] = bad
                result = subprocess.run(args, capture_output=True, text=True,
                                        check=False, timeout=5)
                self.assertEqual(result.returncode, 2, result.stderr)
                self.assertIn("error:", result.stderr)

    def test_cli_help_does_not_fetch_or_require_api_key(self):
        import subprocess
        import sys
        result = subprocess.run(
            [sys.executable, "scripts/disclosure_api.py", "--help"],
            capture_output=True, text=True, check=False)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("--endpoint", result.stdout)
        self.assertIn("--output-dir", result.stdout)

    def test_invalid_json_and_utf8_rejected(self):
        for payload in (b'not-json', b'\\xff\\xfe'):
            with self.subTest(payload=payload), self.assertRaisesRegex(
                    ValueError, "invalid JSON"):
                self.fetch(payload)

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
