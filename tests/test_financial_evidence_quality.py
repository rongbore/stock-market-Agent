import unittest
from scripts.financial_evidence_quality import assess_quality


REF = {"kind": "quarterly_report", "published_date": "2026-10-31",
       "source_url": "https://example.org/q3.pdf"}


def row(**kw):
    r = {"symbol": "000776.SZ", "metric": "revenue", "period": "2026Q3",
         "unit": "CNY_million", "value": 120, "source_ref": REF}
    r.update(kw)
    return r


def payload(*records):
    return {"symbol": "000776.SZ", "metrics": list(records)}


class FinancialEvidenceQualityTests(unittest.TestCase):
    def test_unit_normalization_and_unverified_status(self):
        result = assess_quality(payload(row()))
        self.assertEqual(result["normalized_values_cny"]["revenue:2026Q3"], 120_000_000)
        self.assertEqual(result["status"], "structurally_consistent_unverified")
        self.assertFalse(result["financial_values_verified"])

    def test_negative_revenue_flagged(self):
        result = assess_quality(payload(row(value=-1)))
        self.assertEqual(result["issues"][0]["code"], "negative_nonnegative_metric")

    def test_duplicate_metric_period_flagged(self):
        result = assess_quality(payload(row(), row(unit="CNY_billion")))
        self.assertEqual(result["issues"][0]["code"], "duplicate_metric_period")

    def test_forged_verification_flagged(self):
        result = assess_quality(payload(row(metric_value_verified=True)))
        self.assertEqual(result["issues"][0]["code"], "unsupported_verification_claim")

    def test_bad_period_rejected(self):
        with self.assertRaisesRegex(ValueError, "period"):
            assess_quality(payload(row(period="2026Q5")))

    def test_normalization_overflow_rejected(self):
        with self.assertRaisesRegex(ValueError, "normalized financial value"):
            assess_quality(payload(row(value=1e308, unit="CNY_billion")))

    def test_unhashable_metric_and_unit_rejected_as_value_error(self):
        for changes in ({"metric": ["revenue"]}, {"unit": ["CNY"]},
                        {"metric": {"name": "revenue"}}, {"unit": {"name": "CNY"}}):
            with self.subTest(changes=changes), self.assertRaises(ValueError):
                assess_quality(payload(row(**changes)))

    def test_nan_rejected(self):
        with self.assertRaisesRegex(ValueError, "financial value"):
            assess_quality(payload(row(value=float("nan"))))


if __name__ == "__main__":
    unittest.main()
