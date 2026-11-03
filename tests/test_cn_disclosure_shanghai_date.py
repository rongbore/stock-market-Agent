import unittest

from scripts.cn_disclosures import normalize_disclosure


def sample():
    return dict(
        symbol="000776.SZ",
        title="OFFLINE SYNTHETIC ANNOUNCEMENT",
        provider="synthetic",
        url="https://example.org/notice",
        announcement_date="2026-10-30",
    )


class CNDisclosureShanghaiDateTests(unittest.TestCase):
    def test_utc_timestamp_converts_to_shanghai_date(self):
        record = sample()
        record["published_at"] = "2026-10-29T17:00:00Z"
        normalized = normalize_disclosure(record, analysis_date="2026-10-30")
        self.assertEqual(normalized["announcement_date"], "2026-10-30")
        self.assertFalse(normalized["publication_time_verified"])

    def test_reject_timestamp_that_falls_on_next_shanghai_date(self):
        record = sample()
        record["published_at"] = "2026-10-30T17:00:00Z"
        with self.assertRaises(ValueError):
            normalize_disclosure(record, analysis_date="2026-10-30")

    def test_same_day_publication_remains_unverified(self):
        record = sample()
        record["published_at"] = "2026-10-30T15:00:00+08:00"
        normalized = normalize_disclosure(record, analysis_date="2026-10-30")
        self.assertEqual(normalized["same_day_historical_eligibility"], "unknown")


if __name__ == "__main__":
    unittest.main()
