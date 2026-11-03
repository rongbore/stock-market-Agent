"""Offline end-to-end artifact smoke tests against the current main modules."""
import json
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path

from scripts.provenance import build_manifest, save_manifest
from scripts.report_contract import validate_reports_root
from scripts.source_records import validate_source_record
from scripts.sec_filings import filing_records
from scripts.cn_disclosures import normalize_disclosure


class CombinedSmokeTests(unittest.TestCase):
    def test_report_and_manifest_survive_round_trip(self):
        with tempfile.TemporaryDirectory() as tmp:
            report_dir = Path(tmp) / "NVDA" / "2026-11-04"
            report_dir.mkdir(parents=True)
            (report_dir / "complete_report.html").write_text(
                "<!doctype html><html><body>synthetic fixture</body></html>",
                encoding="utf-8",
            )
            manifest = build_manifest(
                "NVDA", "2026-11-04", "test-only-model",
                generated_at=datetime(2026, 11, 4, tzinfo=timezone.utc),
            )
            manifest_path = save_manifest(report_dir, manifest)
            self.assertEqual(validate_reports_root(tmp), [])
            stored = json.loads(Path(manifest_path).read_text(encoding="utf-8"))
            self.assertEqual(stored["ticker"], "NVDA")
            self.assertFalse(stored["market_data_sources_verified"])
            self.assertEqual(stored["source_records"], [])

    def test_sec_metadata_matches_source_record_schema(self):
        submissions = {
            "cik": 320193,
            "filings": {"recent": {
                "accessionNumber": ["0000320193-26-000001"],
                "primaryDocument": ["report.htm"],
                "form": ["10-K"],
                "acceptanceDateTime": ["2026-10-30T17:00:00"],
            }},
        }
        records = filing_records(
            submissions,
            retrieved_at=datetime(2026, 11, 3, tzinfo=timezone.utc),
        )
        self.assertEqual(len(records), 1)
        self.assertTrue(validate_source_record(
            records[0], analysis_cutoff="2026-10-31T00:00:00+00:00"
        ))

    def test_cn_date_only_cannot_be_claimed_as_verified_source(self):
        disclosure = normalize_disclosure({
            "symbol": "000776.sz",
            "title": "synthetic announcement",
            "provider": "synthetic source",
            "url": "https://example.org/announcement.pdf",
            "announcement_date": "2026-10-30",
        }, analysis_date="2026-10-31")
        self.assertEqual(disclosure["same_day_historical_eligibility"], "unknown")
        with self.assertRaises(ValueError):
            validate_source_record(disclosure)

    def test_missing_html_is_not_masked_by_manifest(self):
        with tempfile.TemporaryDirectory() as tmp:
            save_manifest(tmp, build_manifest(
                "NVDA", "2026-11-04", "test-only-model",
                generated_at=datetime(2026, 11, 4, tzinfo=timezone.utc),
            ))
            self.assertTrue(validate_reports_root(tmp))


if __name__ == "__main__":
    unittest.main()
