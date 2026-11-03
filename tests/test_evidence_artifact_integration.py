import unittest
from pathlib import Path


class EvidenceArtifactIntegrationTests(unittest.TestCase):
    def test_analysis_writes_explicitly_unverified_bundle(self):
        source = (Path(__file__).resolve().parents[1] /
                  "scripts/analyze.py").read_text(encoding="utf-8")
        self.assertIn("validate_evidence_bundle([], analysis_date=trade_date)", source)
        self.assertIn("save_evidence_bundle(", source)

    def test_offline_artifact_checks_evidence_bundle(self):
        workflow = (Path(__file__).resolve().parents[1] /
                    ".github/workflows/offline-artifact-e2e.yml").read_text(encoding="utf-8")
        self.assertIn("evidence_bundle.json", workflow)
        self.assertIn('evidence["source_content_verified"] is False', workflow)
        self.assertIn('evidence["historical_point_in_time_verified"] is False', workflow)


if __name__ == "__main__":
    unittest.main()
