"""Offline cross-module contract checks, without model or market-data calls."""
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path

from scripts.cn_disclosures import normalize_disclosure
from scripts.provenance import build_manifest, save_manifest
from scripts.source_records import validate_source_record


class IntegrationContractTests(unittest.TestCase):
    def setUp(self):
        self.raw = {
            "symbol": "000776.sz",
            "title": "Synthetic test announcement",
            "provider": "Synthetic test provider",
            "url": "https://example.org/announcement.pdf",
            "announcement_date": "2026-10-30",
        }

    def test_date_only_disclosure_is_not_verified_evidence(self):
        disclosure = normalize_disclosure(self.raw, analysis_date="2026-11-01")
        self.assertFalse(disclosure["publication_time_verified"])
        self.assertEqual(disclosure["same_day_historical_eligibility"], "unknown")
        with self.assertRaises(ValueError):
            validate_source_record(disclosure, analysis_cutoff="2026-11-01T23:59:59+08:00")

    def test_verified_metadata_still_requires_explicit_source_fields(self):
        disclosure = normalize_disclosure(self.raw)
        evidence = {
            "kind": "filing",
            "provider": disclosure["provider"],
            "symbol": disclosure["symbol"],
            "url": disclosure["url"],
            "published_at": "2026-10-30T19:00:00+08:00",
            "retrieved_at": "2026-11-03T12:00:00+08:00",
        }
        self.assertTrue(validate_source_record(
            evidence, analysis_cutoff="2026-11-01T23:59:59+08:00"
        ))
        # Passing format checks does NOT authenticate the synthetic timestamps.

    def test_run_manifest_does_not_claim_sources_are_verified(self):
        manifest = build_manifest(
            "000776.SZ", "2026-11-01", "deepseek-flash",
            generated_at=datetime(2026, 11, 3, tzinfo=timezone.utc),
        )
        self.assertFalse(manifest["market_data_sources_verified"])
        self.assertEqual(manifest["source_records"], [])
        with tempfile.TemporaryDirectory() as tmp:
            path = save_manifest(tmp, manifest)
            self.assertTrue(Path(path).is_file())


if __name__ == "__main__":
    unittest.main()
