import unittest
from scripts.fundamental_evidence_ledger import build_ledger


def record(**changes):
    data = {"symbol": "000776.SZ", "kind": "quarterly_report",
            "title": "2026 Q3 report", "published_date": "2026-10-31",
            "source_url": "https://example.org/reports/2026-q3.pdf"}
    data.update(changes)
    return data


class FundamentalEvidenceLedgerTests(unittest.TestCase):
    def test_valid_index_is_not_marked_verified(self):
        result = build_ledger([record()], "000776.SZ")
        self.assertEqual(result["evidence_count"], 1)
        self.assertFalse(result["content_verified"])
        self.assertFalse(result["records"][0]["source_content_verified"])

    def test_symbol_mismatch_rejected(self):
        with self.assertRaisesRegex(ValueError, "symbol mismatch"):
            build_ledger([record(symbol="000001.SZ")], "000776.SZ")

    def test_non_https_rejected(self):
        with self.assertRaisesRegex(ValueError, "HTTPS"):
            build_ledger([record(source_url="http://example.org/report")], "000776.SZ")

    def test_duplicate_rejected(self):
        with self.assertRaisesRegex(ValueError, "duplicate"):
            build_ledger([record(), record()], "000776.SZ")

    def test_invalid_date_rejected(self):
        with self.assertRaisesRegex(ValueError, "date"):
            build_ledger([record(published_date="2026-02-30")], "000776.SZ")

    def test_sort_newest_first(self):
        result = build_ledger([record(published_date="2025-10-31"), record()], "000776.SZ")
        self.assertEqual(result["records"][0]["published_date"], "2026-10-31")


if __name__ == "__main__":
    unittest.main()
