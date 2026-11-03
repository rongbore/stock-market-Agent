import tempfile
import unittest
from pathlib import Path

from scripts.evidence_bundle import save_evidence_bundle, validate_evidence_bundle
from scripts.disclosure_candidates import screen_disclosures, save_disclosure_candidates
from scripts.provenance import build_manifest, save_manifest
from scripts.report_contract import validate_reports_root


class OrphanMetadataTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        good = self.root / "good"
        good.mkdir()
        (good / "complete_report.html").write_text("<html>synthetic</html>", encoding="utf-8")
        save_manifest(good, build_manifest("SYNTHETIC", "2026-01-01", "test"))
        save_evidence_bundle(good, validate_evidence_bundle([], analysis_date="2026-01-01"))

    def test_valid_single_report_passes(self):
        self.assertEqual(validate_reports_root(self.root, require_metadata=True), [])

    def test_orphan_provenance_rejected(self):
        orphan = self.root / "orphan"
        orphan.mkdir()
        save_manifest(orphan, build_manifest("SYNTHETIC", "2026-01-01", "test"))
        self.assertTrue(validate_reports_root(self.root, require_metadata=True))

    def test_orphan_evidence_rejected(self):
        orphan = self.root / "orphan"
        orphan.mkdir()
        save_evidence_bundle(orphan, validate_evidence_bundle([], analysis_date="2026-01-01"))
        self.assertTrue(validate_reports_root(self.root, require_metadata=True))

    def test_orphan_disclosure_candidates_rejected(self):
        orphan = self.root / "orphan"
        orphan.mkdir()
        candidates = screen_disclosures([], analysis_date="2026-01-01",
                                        symbol="000776.SZ")
        save_disclosure_candidates(orphan, candidates)
        self.assertTrue(validate_reports_root(self.root, require_metadata=True))

    def test_non_strict_legacy_behavior_unchanged(self):
        orphan = self.root / "orphan"
        orphan.mkdir()
        save_manifest(orphan, build_manifest("SYNTHETIC", "2026-01-01", "test"))
        self.assertEqual(validate_reports_root(self.root), [])


if __name__ == "__main__":
    unittest.main()
