import json
import tempfile
import unittest
from pathlib import Path

from scripts.disclosure_candidates import screen_disclosures, save_disclosure_candidates
from scripts.evidence_bundle import save_evidence_bundle, validate_evidence_bundle
from scripts.provenance import build_manifest, save_manifest
from scripts.report_contract import validate_reports_root


class DisclosureArtifactContractTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.report = self.root / "report"
        self.report.mkdir()
        (self.report / "complete_report.html").write_text(
            "<html>synthetic</html>", encoding="utf-8")
        save_manifest(self.report, build_manifest("000776.SZ", "2026-10-30", "test"))
        save_evidence_bundle(self.report, validate_evidence_bundle([], analysis_date="2026-10-30"))
        self.notice = dict(symbol="000776.SZ", title="SYNTHETIC NOTICE",
                           provider="synthetic", url="https://example.org/notice",
                           announcement_date="2026-10-29")
        save_disclosure_candidates(
            self.report, screen_disclosures([self.notice],
                                            analysis_date="2026-10-30", symbol="000776.SZ"))

    def check(self):
        return validate_reports_root(self.root, require_metadata=True)

    def edit(self, callback):
        path = self.report / "disclosure_candidates.json"
        data = json.loads(path.read_text(encoding="utf-8"))
        callback(data)
        path.write_text(json.dumps(data), encoding="utf-8")

    def test_valid_candidate_passes(self):
        self.assertEqual(self.check(), [])

    def test_report_symbol_mismatch_rejected(self):
        self.edit(lambda x: x.update(symbol="600519.SS"))
        self.assertTrue(self.check())

    def test_future_announcement_rejected(self):
        self.edit(lambda x: x["candidates"][0].update(announcement_date="2026-11-01"))
        self.assertTrue(self.check())

    def test_forged_eligibility_rejected(self):
        self.edit(lambda x: x["candidates"][0].update(status="verified"))
        self.assertTrue(self.check())

    def test_forged_verification_rejected(self):
        self.edit(lambda x: x.update(source_content_verified=True))
        self.assertTrue(self.check())

    def test_duplicate_candidates_rejected(self):
        self.edit(lambda x: x["candidates"].append(dict(x["candidates"][0])))
        self.assertTrue(self.check())

    def test_tampered_title_rejected(self):
        self.edit(lambda x: x["candidates"][0].update(title=" "))
        self.assertTrue(self.check())

    def test_unexpected_verified_field_rejected(self):
        self.edit(lambda x: x["candidates"][0].update(source_content_verified=True))
        self.assertTrue(self.check())

    def test_forged_publication_time_verification_rejected(self):
        self.edit(lambda x: x["candidates"][0].update(publication_time_verified=True))
        self.assertTrue(self.check())

    def test_invalid_publication_timestamp_rejected(self):
        self.edit(lambda x: x["candidates"][0].update(
            published_at="2026-10-30T01:00:00+08:00"))
        self.assertTrue(self.check())

    def test_absent_optional_candidate_file_passes(self):
        (self.report / "disclosure_candidates.json").unlink()
        self.assertEqual(self.check(), [])


if __name__ == "__main__":
    unittest.main()
