import unittest

from scripts.financial_ai_review_roles import build_specialist_assignments
from scripts.financial_ai_review_roundtable import run_financial_roundtable


class FinancialAiRoundtableTests(unittest.TestCase):
    def _fixture(self):
        files = ["scripts/market_data.py", "scripts/fundamental_metrics.py",
                 "scripts/technical_indicators.py", "scripts/backtest_engine.py",
                 "scripts/portfolio_risk.py"]
        assignments = build_specialist_assignments(files)
        independent = [{"role": item["role"], "verdict": "approve",
                        "summary": item["role"] + " initial review",
                        "findings": []} for item in assignments]
        diffs = {path: "+sample = 1" for path in files}
        return files, independent, diffs

    def test_agents_discuss_in_round_robin_then_moderator_synthesizes(self):
        files, independent, diffs = self._fixture()
        calls = []
        def reviewer(task):
            calls.append(task)
            return {"verdict": "approve", "summary": task["role"] + " discussion complete",
                    "findings": []}
        result = run_financial_roundtable(
            financial_files=files, diff_by_file=diffs,
            independent_reviews=independent, reviewer=reviewer, rounds=2)
        self.assertEqual(len(calls), 11)
        self.assertEqual(result["discussion_rounds"], 2)
        self.assertEqual(len(result["discussion_transcript"]), 10)
        self.assertEqual(calls[-1]["role"], "moderator")
        self.assertEqual(result["overall_verdict"], "approve")
        self.assertFalse(result["merge_authorized"])

    def test_dissent_cannot_be_erased_by_moderator(self):
        files, independent, diffs = self._fixture()
        independent[0]["verdict"] = "uncertain"
        def reviewer(task):
            return {"verdict": "approve", "summary": "all good",
                    "findings": []}
        result = run_financial_roundtable(
            financial_files=files, diff_by_file=diffs,
            independent_reviews=independent, reviewer=reviewer, rounds=1)
        self.assertEqual(result["overall_verdict"], "uncertain")
        self.assertTrue(result["dissent_preserved"])
        self.assertTrue(result["unresolved_disagreement"])

    def test_high_severity_finding_blocks_moderator_approval(self):
        files, independent, diffs = self._fixture()
        independent[0]["findings"] = [{"severity": "critical",
                                       "path": files[0], "explanation": "evidence-backed issue"}]
        def reviewer(task):
            return {"verdict": "approve", "summary": "approved",
                    "findings": []}
        result = run_financial_roundtable(
            financial_files=files, diff_by_file=diffs,
            independent_reviews=independent, reviewer=reviewer, rounds=1)
        self.assertEqual(result["overall_verdict"], "request_changes")

    def test_rejects_invalid_round_count_and_unassigned_finding(self):
        files, independent, diffs = self._fixture()
        independent[0]["findings"] = [{"severity": "high", "path": "other.py",
                                       "explanation": "bad"}]
        with self.assertRaises(ValueError):
            run_financial_roundtable(financial_files=files, diff_by_file=diffs,
                                     independent_reviews=independent,
                                     reviewer=lambda _: {}, rounds=1)
        independent[0]["findings"] = []
        with self.assertRaisesRegex(ValueError, "round count"):
            run_financial_roundtable(financial_files=files, diff_by_file=diffs,
                                     independent_reviews=independent,
                                     reviewer=lambda _: {}, rounds=3)


if __name__ == "__main__":
    unittest.main()
