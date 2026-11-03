import unittest

from scripts.source_records import validate_source_record


def sample():
    return {
        "kind": "filing",
        "provider": "Example official filing source",
        "symbol": "000776.SZ",
        "url": "https://example.org/filing",
        "published_at": "2026-10-30T16:00:00+08:00",
        "retrieved_at": "2026-11-03T10:00:00+08:00",
    }


class SourceRecordTests(unittest.TestCase):
    def test_valid(self):
        self.assertTrue(validate_source_record(sample()))

    def test_missing_published_at(self):
        record = sample()
        del record["published_at"]
        with self.assertRaises(ValueError):
            validate_source_record(record)

    def test_reject_future_information(self):
        with self.assertRaises(ValueError):
            validate_source_record(sample(), analysis_cutoff="2026-10-29T23:59:59+08:00")

    def test_reject_non_https(self):
        record = sample()
        record["url"] = "http://example.org"
        with self.assertRaises(ValueError):
            validate_source_record(record)

    def test_reject_url_credentials(self):
        record = sample()
        record["url"] = "https://user:secret@example.org/data"
        with self.assertRaises(ValueError):
            validate_source_record(record)

    def test_reject_naive_timestamp(self):
        record = sample()
        record["published_at"] = "2026-10-30T16:00:00"
        with self.assertRaises(ValueError):
            validate_source_record(record)

    def test_reject_published_after_retrieval(self):
        record = sample()
        record["published_at"] = "2026-11-04T00:00:00+08:00"
        with self.assertRaises(ValueError):
            validate_source_record(record)


if __name__ == "__main__":
    unittest.main()
