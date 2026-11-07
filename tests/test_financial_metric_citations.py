import unittest
from scripts.financial_metric_citations import link_metrics


REF = {"kind": "quarterly_report", "published_date": "2026-10-31",
       "source_url": "https://example.org/2026-q3.pdf"}


def ledger():
    return {"symbol": "000776.SZ", "records": [dict(REF, symbol="000776.SZ")]}


def metric(**changes):
    row = {"symbol": "000776.SZ", "metric": "revenue", "period": "2026Q3",
           "value": 123.4, "unit": "CNY_million", "source_ref": dict(REF)}
    row.update(changes)
    return row


class FinancialMetricCitationTests(unittest.TestCase):
    def test_link_preserves_unverified_boundary(self):
        result = link_metrics(ledger(), [metric()])
        self.assertEqual(result["metric_count"], 1)
        self.assertFalse(result["all_metrics_verified"])
        self.assertFalse(result["metrics"][0]["metric_value_verified"])

    def test_missing_reference_rejected(self):
        row = metric(source_ref=dict(REF, source_url="https://example.org/other.pdf"))
        with self.assertRaisesRegex(ValueError, "not in ledger"):
            link_metrics(ledger(), [row])

    def test_symbol_mismatch_rejected(self):
        with self.assertRaisesRegex(ValueError, "symbol mismatch"):
            link_metrics(ledger(), [metric(symbol="000001.SZ")])

    def test_invalid_numeric_rejected(self):
        with self.assertRaisesRegex(ValueError, "invalid financial value"):
            link_metrics(ledger(), [metric(value=float("nan"))])

    def test_duplicate_metric_rejected(self):
        with self.assertRaisesRegex(ValueError, "duplicate financial metric"):
            link_metrics(ledger(), [metric(), metric()])

    def test_unsupported_unit_rejected(self):
        with self.assertRaisesRegex(ValueError, "unsupported"):
            link_metrics(ledger(), [metric(unit="USD")])


if __name__ == "__main__":
    unittest.main()
