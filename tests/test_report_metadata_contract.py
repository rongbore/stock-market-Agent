import json
import tempfile
import unittest
from pathlib import Path

from scripts.evidence_bundle import validate_evidence_bundle, save_evidence_bundle
from scripts.provenance import build_manifest, save_manifest
from scripts.report_contract import validate_reports_root


class ReportMetadataContractTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.folder = self.root / "SYNTHETIC" / "2026-01-01"
        self.folder.mkdir(parents=True)
        (self.folder / "complete_report.html").write_text(
            "<html><body>OFFLINE SYNTHETIC TEST ONLY</body></html>", encoding="utf-8"
        )

    def write_metadata(self):
        save_manifest(self.folder, build_manifest("SYNTHETIC", "2026-01-01", "offline"))
        save_evidence_bundle(
            self.folder, validate_evidence_bundle([], analysis_date="2026-01-01")
        )

    def test_missing_metadata_blocks_strict_upload(self):
        self.assertEqual(validate_reports_root(self.root), [])
        self.assertTrue(validate_reports_root(self.root, require_metadata=True))

    def test_matching_metadata_passes(self):
        self.write_metadata()
        self.assertEqual(validate_reports_root(self.root, require_metadata=True), [])

    def test_mismatched_analysis_date_blocks_upload(self):
        self.write_metadata()
        path = self.folder / "evidence_bundle.json"
        payload = json.loads(path.read_text(encoding="utf-8"))
        payload["analysis_date"] = "2026-01-02"
        path.write_text(json.dumps(payload), encoding="utf-8")
        self.assertTrue(validate_reports_root(self.root, require_metadata=True))

    def test_false_verification_claim_blocks_upload(self):
        self.write_metadata()
        path = self.folder / "evidence_bundle.json"
        payload = json.loads(path.read_text(encoding="utf-8"))
        payload["source_content_verified"] = True
        path.write_text(json.dumps(payload), encoding="utf-8")
        self.assertTrue(validate_reports_root(self.root, require_metadata=True))

    def test_invalid_json_blocks_upload(self):
        self.write_metadata()
        (self.folder / "run_provenance.json").write_text("{", encoding="utf-8")
        self.assertTrue(validate_reports_root(self.root, require_metadata=True))


if __name__ == "__main__":
    unittest.main()
