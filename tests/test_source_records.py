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

    def test_reject_unhashable_source_kind(self):
        for kind in (["filing"], {"name": "filing"}, None, 123):
            with self.subTest(kind=kind):
                record = sample()
                record["kind"] = kind
                with self.assertRaisesRegex(ValueError, "unsupported source kind"):
                    validate_source_record(record)

    def test_missing_published_at(self):
        record = sample()
        del record["published_at"]
        with self.assertRaises(ValueError):
            validate_source_record(record)

    def test_reject_future_information(self):
        with self.assertRaises(ValueError):
            validate_source_record(sample(), analysis_cutoff="2026-10-29T23:59:59+08:00")

    def test_reject_retrieval_after_historical_cutoff(self):
        record = sample()
        with self.assertRaisesRegex(ValueError, "retrieved after"):
            validate_source_record(record, analysis_cutoff="2026-10-31T23:59:59+08:00", require_retrieved_by_cutoff=True)

    def test_accept_retrieval_within_historical_cutoff(self):
        record = sample()
        record["retrieved_at"] = "2026-10-30T17:00:00+08:00"
        self.assertTrue(validate_source_record(
            record, analysis_cutoff="2026-10-31T23:59:59+08:00", require_retrieved_by_cutoff=True))

    def test_retrospective_retrieval_remains_allowed_but_unverified(self):
        self.assertTrue(validate_source_record(
            sample(), analysis_cutoff="2026-10-31T23:59:59+08:00"))

    def test_strict_retrieval_requires_explicit_cutoff(self):
        with self.assertRaisesRegex(ValueError, "requires analysis_cutoff"):
            validate_source_record(sample(), require_retrieved_by_cutoff=True)

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

    def test_reject_control_characters_in_source_url(self):
        for url in ("https://example.org/a\nb", "https://example.org/a\tb",
                    "https://example.org/a b", "https://example.org/a\x7fb"):
            with self.subTest(url=url):
                record = sample()
                record["url"] = url
                with self.assertRaisesRegex(ValueError, "control characters"):
                    validate_source_record(record)

    def test_reject_malformed_url_ports(self):
        for url in ("https://example.org:abc/data", "https://example.org:99999/data"):
            with self.subTest(url=url):
                record = sample()
                record["url"] = url
                with self.assertRaisesRegex(ValueError, "invalid source URL"):
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
