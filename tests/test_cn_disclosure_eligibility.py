import unittest

from scripts.cn_disclosures import historical_disclosure_eligibility


def sample(date="2026-10-30"):
    return {
        "symbol": "000776.SZ",
        "title": "SYNTHETIC NOTICE",
        "provider": "synthetic",
        "url": "https://example.org/notice",
        "announcement_date": date,
    }


class HistoricalDisclosureEligibilityTests(unittest.TestCase):
    def test_prior_day_is_candidate_not_verified(self):
        result = historical_disclosure_eligibility(
            sample(), analysis_date="2026-10-31")
        self.assertTrue(result["eligible_by_announcement_date"])
        self.assertEqual(result["status"], "prior_date_candidate")
        self.assertFalse(result["historical_point_in_time_verified"])

    def test_same_day_date_only_is_blocked(self):
        result = historical_disclosure_eligibility(
            sample(), analysis_date="2026-10-30")
        self.assertFalse(result["eligible_by_announcement_date"])
        self.assertEqual(result["status"], "same_day_requires_verification")

    def test_same_day_claimed_timestamp_still_requires_verification(self):
        record = sample()
        record["published_at"] = "2026-10-30T08:00:00+08:00"
        result = historical_disclosure_eligibility(
            record, analysis_date="2026-10-30")
        self.assertFalse(result["eligible_by_announcement_date"])
        self.assertFalse(result["historical_point_in_time_verified"])

    def test_future_announcement_rejected(self):
        with self.assertRaises(ValueError):
            historical_disclosure_eligibility(
                sample("2026-11-01"), analysis_date="2026-10-30")

    def test_utc_timestamp_previous_day_in_shanghai(self):
        record = sample()
        record["published_at"] = "2026-10-29T17:00:00Z"
        result = historical_disclosure_eligibility(
            record, analysis_date="2026-10-31")
        self.assertTrue(result["eligible_by_announcement_date"])


if __name__ == "__main__":
    unittest.main()
