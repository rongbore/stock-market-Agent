"""Offline tests: no TradingAgents installation or API key needed."""
import json
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

from scripts.provenance import build_manifest, save_manifest


class ProvenanceTests(unittest.TestCase):
    def test_manifest_has_explicit_unverified_sources(self):
        manifest = build_manifest(
            "000776.SZ", "2026-11-03", "deepseek-flash",
            generated_at=datetime(2026, 11, 3, 12, 0, tzinfo=timezone.utc),
            run_id="123",
        )
        self.assertFalse(manifest["market_data_sources_verified"])
        self.assertEqual(manifest["source_records"], [])
        self.assertEqual(manifest["github_run_id"], "123")
        self.assertEqual(manifest["generated_at_utc"], "2026-11-03T12:00:00+00:00")

    def test_timezone_is_normalized(self):
        tz = timezone(timedelta(hours=8))
        manifest = build_manifest("NVDA", "2026-11-03", "model",
                                  generated_at=datetime(2026, 11, 3, 20, tzinfo=tz))
        self.assertEqual(manifest["generated_at_utc"], "2026-11-03T12:00:00+00:00")

    def test_rejects_naive_timestamp(self):
        with self.assertRaises(ValueError):
            build_manifest("NVDA", "2026-11-03", "model",
                           generated_at=datetime(2026, 11, 3))

    def test_write_json(self):
        with tempfile.TemporaryDirectory() as directory:
            path = save_manifest(directory, build_manifest("NVDA", "2026-11-03", "model"))
            self.assertEqual(path.name, "run_provenance.json")
            data = json.loads(Path(path).read_text(encoding="utf-8"))
            self.assertEqual(data["ticker"], "NVDA")


if __name__ == "__main__":
    unittest.main()
