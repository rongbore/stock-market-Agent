import unittest
from scripts.financial_claim_evidence import validate_claims


class FinancialClaimEvidenceTests(unittest.TestCase):
    def setUp(self):
        self.fp = [{"symbol": "000776.SZ", "file_sha256": "a" * 64,
                    "official_origin_verified": False, "source_content_verified": False}]
        self.claim = {"symbol": "000776.SZ", "metric": "revenue", "value": "123.45",
                      "unit": "CNY_100000000", "period_end": "2026-09-30",
                      "announcement_date": "2026-10-20", "file_sha256": "a" * 64,
                      "page": 4}

    def test_valid_claim_is_explicitly_unverified(self):
        result = validate_claims([self.claim], self.fp, "000776.SZ", "2026-10-30")
        self.assertEqual(result[0]["status"], "manually_transcribed_unverified")
        self.assertFalse(result[0]["source_content_verified"])

    def test_reject_future_disclosure(self):
        claim = dict(self.claim, announcement_date="2026-11-01")
        with self.assertRaisesRegex(ValueError, "cutoff"):
            validate_claims([claim], self.fp, "000776.SZ", "2026-10-30")

    def test_reject_unmatched_file(self):
        claim = dict(self.claim, file_sha256="b" * 64)
        with self.assertRaisesRegex(ValueError, "matching"):
            validate_claims([claim], self.fp, "000776.SZ", "2026-10-30")

    def test_reject_missing_page_or_bad_number(self):
        for claim in (dict(self.claim, page=0), dict(self.claim, value="1e100"),
                      dict(self.claim, value="NaN")):
            with self.subTest(claim=claim), self.assertRaises(ValueError):
                validate_claims([claim], self.fp, "000776.SZ", "2026-10-30")

    def test_reject_false_verified_fingerprint(self):
        fp = [dict(self.fp[0], official_origin_verified=True)]
        with self.assertRaisesRegex(ValueError, "verification claim"):
            validate_claims([self.claim], fp, "000776.SZ", "2026-10-30")


if __name__ == "__main__":
    unittest.main()
