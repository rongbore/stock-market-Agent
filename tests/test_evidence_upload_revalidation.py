import json
import tempfile
import unittest
from pathlib import Path

from scripts.evidence_bundle import validate_evidence_bundle, save_evidence_bundle
from scripts.provenance import build_manifest, save_manifest
from scripts.report_contract import validate_reports_root


class EvidenceUploadRevalidationTests(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name)
        self.directory = self.root / "SYNTHETIC"
        self.directory.mkdir()
        (self.directory / "complete_report.html").write_text(
            "<html>synthetic</html>", encoding="utf-8")
        save_manifest(self.directory, build_manifest("SYNTHETIC", "2026-01-01", "test"))
        save_evidence_bundle(
            self.directory, validate_evidence_bundle([], analysis_date="2026-01-01"))

    def mutate(self, change):
        path = self.directory / "evidence_bundle.json"
        payload = json.loads(path.read_text(encoding="utf-8"))
        change(payload)
        path.write_text(json.dumps(payload), encoding="utf-8")

    def test_valid_artifact_passes(self):
        self.assertEqual(validate_reports_root(self.root, require_metadata=True), [])

    def test_tampered_future_cutoff_rejected(self):
        self.mutate(lambda x: x.update(analysis_cutoff="2026-01-02T23:00:00+08:00"))
        self.assertTrue(validate_reports_root(self.root, require_metadata=True))

    def test_tampered_future_record_rejected_even_if_both_lists_match(self):
        record = dict(kind="news", provider="synthetic", symbol="SYNTHETIC",
                      url="https://example.org/news",
                      published_at="2026-01-02T12:00:00+08:00",
                      retrieved_at="2026-01-03T12:00:00+08:00")
        self.mutate(lambda x: x.update(records=[record]))
        path = self.directory / "run_provenance.json"
        manifest = json.loads(path.read_text(encoding="utf-8"))
        manifest["source_records"] = [record]
        path.write_text(json.dumps(manifest), encoding="utf-8")
        self.assertTrue(validate_reports_root(self.root, require_metadata=True))

    def test_missing_validation_marker_rejected(self):
        self.mutate(lambda x: x.pop("metadata_validated"))
        self.assertTrue(validate_reports_root(self.root, require_metadata=True))

    def test_cutoff_after_analysis_date_rejected_at_source(self):
        with self.assertRaises(ValueError):
            validate_evidence_bundle([], analysis_date="2026-01-01",
                                     cutoff="2026-01-02T00:00:00+08:00")


if __name__ == "__main__":
    unittest.main()
