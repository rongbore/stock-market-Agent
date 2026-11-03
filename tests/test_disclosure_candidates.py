import json
import tempfile
import unittest
from pathlib import Path

from scripts.disclosure_candidates import screen_disclosures, save_disclosure_candidates


def notice(day):
    return {
        "symbol": "000776.sz",
        "title": "SYNTHETIC DISCLOSURE",
        "provider": "synthetic",
        "url": "https://example.org/notice",
        "announcement_date": day,
    }


class DisclosureCandidateExportTests(unittest.TestCase):
    def test_prior_day_is_candidate_but_not_verified(self):
        result = screen_disclosures([notice("2026-10-29")],
                                    analysis_date="2026-10-30", symbol="000776.SZ")
        self.assertTrue(result["candidates"][0]["eligible_by_announcement_date"])
        self.assertFalse(result["historical_point_in_time_verified"])
        self.assertFalse(result["source_content_verified"])

    def test_same_day_not_eligible(self):
        result = screen_disclosures([notice("2026-10-30")],
                                    analysis_date="2026-10-30", symbol="000776.SZ")
        self.assertFalse(result["candidates"][0]["eligible_by_announcement_date"])

    def test_future_date_rejected(self):
        with self.assertRaises(ValueError):
            screen_disclosures([notice("2026-10-31")],
                               analysis_date="2026-10-30", symbol="000776.SZ")

    def test_wrong_symbol_rejected(self):
        with self.assertRaises(ValueError):
            screen_disclosures([notice("2026-10-29")],
                               analysis_date="2026-10-30", symbol="600519.SS")

    def test_duplicate_notice_rejected(self):
        with self.assertRaisesRegex(ValueError, "duplicate"):
            screen_disclosures([notice("2026-10-29"), notice("2026-10-29")],
                               analysis_date="2026-10-30", symbol="000776.SZ")

    def test_publication_timestamp_preserved_but_unverified(self):
        record = notice("2026-10-29")
        record["published_at"] = "2026-10-29T16:00:00+08:00"
        result = screen_disclosures([record], analysis_date="2026-10-30",
                                    symbol="000776.SZ")
        candidate = result["candidates"][0]
        self.assertEqual(candidate["published_at"], record["published_at"])
        self.assertFalse(candidate["publication_time_verified"])
        self.assertFalse(candidate["historical_point_in_time_verified"])

    def test_timestamp_date_mismatch_rejected(self):
        record = notice("2026-10-29")
        record["published_at"] = "2026-10-30T00:30:00+08:00"
        with self.assertRaisesRegex(ValueError, "disagree"):
            screen_disclosures([record], analysis_date="2026-10-30",
                               symbol="000776.SZ")

    def test_json_export(self):
        with tempfile.TemporaryDirectory() as tmp:
            result = screen_disclosures([], analysis_date="2026-10-30",
                                        symbol="000776.SZ")
            path = save_disclosure_candidates(tmp, result)
            self.assertEqual(json.loads(path.read_text(encoding="utf-8"))["candidates"], [])
            self.assertEqual(path.name, "disclosure_candidates.json")

    def test_invalid_input_rejected(self):
        with self.assertRaises(ValueError):
            screen_disclosures({}, analysis_date="2026-10-30", symbol="000776.SZ")


if __name__ == "__main__":
    unittest.main()
