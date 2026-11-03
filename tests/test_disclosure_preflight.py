import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from scripts.analyze import load_disclosure_candidates, main


class DisclosurePreflightTests(unittest.TestCase):
    def test_unset_is_noop(self):
        with patch.dict(os.environ, {}, clear=True):
            self.assertIsNone(load_disclosure_candidates("000776.SZ", "2026-10-30"))

    def test_valid_prior_day_candidate(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "notices.json"
            path.write_text(json.dumps([{
                "symbol": "000776.SZ", "title": "SYNTHETIC",
                "provider": "test", "url": "https://example.org/test",
                "announcement_date": "2026-10-29"
            }]), encoding="utf-8")
            with patch.dict(os.environ, {"ANALYSIS_DISCLOSURES_JSON": str(path)}):
                result = load_disclosure_candidates("000776.SZ", "2026-10-30")
            self.assertEqual(len(result["candidates"]), 1)
            self.assertFalse(result["source_content_verified"])

    def test_invalid_metadata_fails_before_api_key_check(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "notices.json"
            path.write_text(json.dumps([{
                "symbol": "000776.SZ", "title": "SYNTHETIC",
                "provider": "test", "url": "https://example.org/test",
                "announcement_date": "2026-10-31"
            }]), encoding="utf-8")
            with patch.dict(os.environ, {
                "ANALYSIS_DISCLOSURES_JSON": str(path),
                "ANALYSIS_TICKER": "000776.SZ",
                "ANALYSIS_DATE": "2026-10-30",
                "DEEPSEEK_API_KEY": "",
            }, clear=True):
                with self.assertRaisesRegex(ValueError, "after analysis date"):
                    main()

    def test_missing_file_fails_before_api_key_check(self):
        with patch.dict(os.environ, {
            "ANALYSIS_DISCLOSURES_JSON": "/nonexistent/synthetic-disclosures.json",
            "ANALYSIS_TICKER": "000776.SZ",
            "ANALYSIS_DATE": "2026-10-30",
            "DEEPSEEK_API_KEY": "",
        }, clear=True):
            with self.assertRaises(FileNotFoundError):
                main()


if __name__ == "__main__":
    unittest.main()
