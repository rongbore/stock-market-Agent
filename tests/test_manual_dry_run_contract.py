"""Prevent manual dry-run workflow from drifting away from strict report contract."""
import unittest
from pathlib import Path


class ManualDryRunWorkflowContractTests(unittest.TestCase):
    def test_synthetic_workflow_creates_evidence_before_strict_validation(self):
        text = (Path(__file__).resolve().parents[1] /
                ".github/workflows/analyze.yml").read_text(encoding="utf-8")
        start = text.index("      - name: Create synthetic report fixture")
        end = text.index("      - name: Validate synthetic report artifacts", start)
        fixture = text[start:end]
        self.assertIn("from scripts.evidence_bundle import validate_evidence_bundle, save_evidence_bundle", fixture)
        self.assertIn('save_evidence_bundle(root, validate_evidence_bundle([], analysis_date="2026-01-01"))', fixture)
        self.assertIn("python scripts/report_contract.py results/reports --require-metadata",
                      text[end:])


if __name__ == "__main__":
    unittest.main()
