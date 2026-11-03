import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from scripts.analyze import load_disclosure_candidates


class OfficialSourcePreflightTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.path = Path(temporary.name) / "notices.json"
        self.record = {
            "symbol": "000776.SZ", "title": "SYNTHETIC NOTICE",
            "url": "https://static.cninfo.com.cn/finalpage/test.pdf",
            "announcement_date": "2026-10-29",
        }

    def load(self, source="cninfo"):
        with patch.dict(os.environ, {
            "ANALYSIS_DISCLOSURES_JSON": str(self.path),
            "ANALYSIS_DISCLOSURE_SOURCE": source,
        }):
            return load_disclosure_candidates("000776.SZ", "2026-10-30")

    def test_official_notice_screened_before_model(self):
        self.path.write_text(json.dumps([self.record]), encoding="utf-8")
        result = self.load()
        self.assertEqual(result["candidates"][0]["provider"], "CNINFO")
        self.assertFalse(result["source_content_verified"])

    def test_lookalike_host_rejected(self):
        self.record["url"] = "https://static.cninfo.com.cn.evil.example/test.pdf"
        self.path.write_text(json.dumps([self.record]), encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "official HTTPS host"):
            self.load()

    def test_official_source_requires_list(self):
        self.path.write_text(json.dumps({"notice": self.record}), encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "list"):
            self.load()

    def test_wrong_exchange_rejected(self):
        self.record["url"] = "https://www.sse.com.cn/test.pdf"
        self.path.write_text(json.dumps([self.record]), encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "SSE notice"):
            self.load("sse")


if __name__ == "__main__":
    unittest.main()
