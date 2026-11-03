import unittest
from datetime import datetime, timezone

from scripts.sec_filings import filing_records


def sample():
    return {
        "cik": 320193,
        "filings": {"recent": {
            "accessionNumber": ["0000320193-26-000001"],
            "primaryDocument": ["report.htm"],
            "form": ["10-K"],
            "acceptanceDateTime": ["2026-10-30T17:00:00"],
        }},
    }


class SECAdapterTests(unittest.TestCase):
    def setUp(self):
        self.retrieved = datetime(2026, 11, 3, tzinfo=timezone.utc)

    def test_builds_official_archive_url(self):
        record = filing_records(sample(), retrieved_at=self.retrieved)[0]
        self.assertEqual(record["provider"], "SEC EDGAR")
        self.assertEqual(record["url"],
                         "https://www.sec.gov/Archives/edgar/data/320193/000032019326000001/report.htm")

    def test_converts_eastern_to_utc(self):
        record = filing_records(sample(), retrieved_at=self.retrieved)[0]
        self.assertEqual(record["published_at"], "2026-10-30T21:00:00+00:00")

    def test_historical_cutoff_filters_later_filing(self):
        cutoff = datetime(2026, 10, 30, 20, tzinfo=timezone.utc)
        self.assertEqual(filing_records(sample(), retrieved_at=self.retrieved, cutoff=cutoff), [])

    def test_rejects_misaligned_arrays(self):
        data = sample()
        data["filings"]["recent"]["form"] = []
        with self.assertRaises(ValueError):
            filing_records(data, retrieved_at=self.retrieved)

    def test_rejects_path_traversal(self):
        data = sample()
        data["filings"]["recent"]["primaryDocument"] = ["../secret"]
        with self.assertRaises(ValueError):
            filing_records(data, retrieved_at=self.retrieved)

    def test_rejects_future_retrieval(self):
        with self.assertRaises(ValueError):
            filing_records(sample(), retrieved_at=datetime(2026, 10, 29, tzinfo=timezone.utc))

    def test_requires_timezone(self):
        with self.assertRaises(ValueError):
            filing_records(sample(), retrieved_at=datetime(2026, 11, 3))


if __name__ == "__main__":
    unittest.main()
