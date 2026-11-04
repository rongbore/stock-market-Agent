import unittest
from scripts.financial_claim_evidence import validate_claims

class FinancialClaimBoundaryTests(unittest.TestCase):
    def setUp(self):
        self.fp = {"symbol": "000776.SZ", "file_sha256": "b"*64, "announcement_date": "2026-10-20", "official_origin_verified": False, "source_content_verified": False}
        self.claim = {"symbol": "000776.SZ", "metric": "revenue", "value": "123.45", "unit": "CNY", "period_end": "2026-09-30", "announcement_date": "2026-10-20", "file_sha256": "b"*64, "page": 4}

    def check(self, cutoff="2026-10-20", claim=None, fp=None):
        return validate_claims([claim or self.claim], [fp or self.fp], "000776.SZ", cutoff)

    def test_cutoff_day_remains_unverified(self):
        row = self.check()[0]
        self.assertEqual(row["status"], "manually_transcribed_unverified")
        self.assertFalse(row["historical_point_in_time_verified"])

    def test_before_announcement_rejected(self):
        with self.assertRaises(ValueError):
            self.check(cutoff="2026-10-19")

    def test_future_period_rejected(self):
        with self.assertRaises(ValueError):
            self.check(claim=dict(self.claim, period_end="2026-10-21"))

    def test_noncanonical_cutoff_rejected(self):
        for cutoff in ("2026-2-01", "2026-02-30", "2026-10-20T00:00:00"):
            with self.subTest(cutoff=cutoff), self.assertRaises(ValueError):
                self.check(cutoff=cutoff)

    def test_wrong_symbol_rejected(self):
        with self.assertRaises(ValueError):
            self.check(fp=dict(self.fp, symbol="600519.SS"))

    def test_false_verification_rejected(self):
        with self.assertRaises(ValueError):
            self.check(fp=dict(self.fp, official_origin_verified=True))

if __name__ == "__main__":
    unittest.main()
