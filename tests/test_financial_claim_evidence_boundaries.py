"""Offline boundary regression tests for manually transcribed financial evidence.

These tests use synthetic values only; no official-source authenticity is implied.
"""
import unittest

from scripts.financial_claim_evidence import validate_claims


class FinancialEvidenceBoundaryTests(unittest.TestCase):
    def setUp(self):
        self.symbol = "000776.SZ"
        self.digest = "a" * 64
        self.fingerprint = {
            "symbol": self.symbol,
            "file_sha256": self.digest,
            "announcement_date": "2026-10-20",
            "official_origin_verified": False,
            "source_content_verified": False,
        }
        self.claim = {
            "symbol": self.symbol,
            "metric": "revenue",
            "value": "123.45",
            "unit": "CNY_100000000",
            "period_end": "2026-09-30",
            "announcement_date": "2026-10-20",
            "file_sha256": self.digest,
            "page": 4,
        }

    def validate(self, claims=None, fingerprints=None, cutoff="2026-10-20"):
        return validate_claims(
            [self.claim] if claims is None else claims,
            [self.fingerprint] if fingerprints is None else fingerprints,
            self.symbol, cutoff,
        )

    def test_disclosure_on_cutoff_is_allowed_but_remains_unverified(self):
        record = self.validate()[0]
        self.assertEqual(record["announcement_date"], "2026-10-20")
        self.assertEqual(record["status"], "manually_transcribed_unverified")
        for flag in ("official_origin_verified", "source_content_verified",
                     "historical_point_in_time_verified"):
            self.assertIs(record[flag], False)

    def test_disclosure_one_day_after_cutoff_is_rejected(self):
        with self.assertRaises(ValueError):
            self.validate(cutoff="2026-10-19")

    def test_reject_boolean_pdf_page(self):
        with self.assertRaisesRegex(ValueError, "PDF page"):
            self.validate(claims=[dict(self.claim, page=True)])

    def test_reject_noncanonical_dates_and_sha(self):
        cases = [
            ([dict(self.claim, period_end="2026-9-30")], None),
            (None, [dict(self.fingerprint, announcement_date="2026-10-2")]),
            (None, [dict(self.fingerprint, file_sha256="A" * 64)]),
        ]
        for claims, fingerprints in cases:
            with self.subTest(claims=claims, fingerprints=fingerprints):
                with self.assertRaises(ValueError):
                    self.validate(claims=claims, fingerprints=fingerprints)

    def test_reject_more_than_one_hundred_claims_or_fingerprints(self):
        with self.assertRaisesRegex(ValueError, "at most 100"):
            self.validate(claims=[self.claim] * 101)
        with self.assertRaisesRegex(ValueError, "at most 100"):
            self.validate(fingerprints=[self.fingerprint] * 101)


if __name__ == "__main__":
    unittest.main()
