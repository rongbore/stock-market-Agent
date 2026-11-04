import json
import tempfile
import unittest
from pathlib import Path

from scripts.evidence_bundle import validate_evidence_bundle, save_evidence_bundle


def example():
    return {
        "kind": "filing",
        "provider": "Synthetic provider",
        "symbol": "000776.SZ",
        "url": "https://example.org/synthetic",
        "published_at": "2026-10-30T16:00:00+08:00",
        "retrieved_at": "2026-11-03T10:00:00+08:00",
    }


class EvidenceBundleTests(unittest.TestCase):
    def test_valid_metadata_does_not_claim_verified_content(self):
        bundle = validate_evidence_bundle([example()], analysis_date="2026-10-31")
        self.assertTrue(bundle["metadata_validated"])
        self.assertFalse(bundle["source_content_verified"])
        self.assertFalse(bundle["historical_point_in_time_verified"])

    def test_rejects_noncanonical_analysis_date(self):
        for invalid in ("20261031", "2026-W44-6", "2026-02-30", "", None, 20261031):
            with self.subTest(invalid=invalid):
                with self.assertRaisesRegex(ValueError, "analysis_date"):
                    validate_evidence_bundle([example()], analysis_date=invalid)

    def test_rejects_invalid_cutoff_types_and_dates(self):
        for invalid in (None,):
            # None intentionally selects the documented default cutoff.
            self.assertTrue(validate_evidence_bundle(
                [example()], analysis_date="2026-10-31", cutoff=invalid))
        for invalid in (42, {}, "", "not-a-date"):
            with self.subTest(invalid=invalid):
                with self.assertRaisesRegex(ValueError, "cutoff"):
                    validate_evidence_bundle(
                        [example()], analysis_date="2026-10-31", cutoff=invalid)

    def test_future_publication_rejected(self):
        record = example()
        record["published_at"] = "2026-11-01T00:00:00+08:00"
        with self.assertRaises(ValueError):
            validate_evidence_bundle([record], analysis_date="2026-10-31")

    def test_duplicate_evidence_rejected(self):
        with self.assertRaises(ValueError):
            validate_evidence_bundle([example(), example()], analysis_date="2026-10-31")

    def test_intraday_cutoff(self):
        with self.assertRaises(ValueError):
            validate_evidence_bundle(
                [example()], analysis_date="2026-10-30",
                cutoff="2026-10-30T15:00:00+08:00")

    def test_rejects_date_only_disclosure(self):
        with self.assertRaises(ValueError):
            validate_evidence_bundle([{
                "symbol": "000776.SZ", "url": "https://example.org/notice",
                "announcement_date": "2026-10-30",
            }], analysis_date="2026-10-31")

    def test_roundtrip(self):
        with tempfile.TemporaryDirectory() as tmp:
            bundle = validate_evidence_bundle([example()], analysis_date="2026-10-31")
            path = save_evidence_bundle(tmp, bundle)
            self.assertEqual(json.loads(Path(path).read_text())["records"], [example()])


if __name__ == "__main__":
    unittest.main()
