"""Guard the optional disclosure hook against accidental promotion to verified evidence."""
import unittest
from pathlib import Path


class OptionalDisclosureHookTests(unittest.TestCase):
    def test_entrypoint_preflights_before_model_and_attaches_after_report(self):
        source = (Path(__file__).resolve().parents[1] /
                  "scripts/analyze.py").read_text(encoding="utf-8")
        self.assertIn('os.environ.get("ANALYSIS_DISCLOSURES_JSON", "")', source)
        self.assertIn("screen_disclosures(records, analysis_date=trade_date, symbol=ticker)", source)
        self.assertIn("save_disclosure_candidates(report_dir, candidates)", source)
        self.assertLess(source.index("candidates = load_disclosure_candidates(ticker, trade_date)"),
                        source.index("graph.propagate("))
        self.assertLess(source.index("graph.save_reports("),
                        source.index("save_disclosure_candidates(report_dir, candidates)"))
        self.assertLess(source.index("save_evidence_bundle("),
                        source.index("save_disclosure_candidates(report_dir, candidates)"))
        self.assertIn("validate_evidence_bundle([], analysis_date=trade_date)", source)


if __name__ == "__main__":
    unittest.main()
