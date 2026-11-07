import unittest

from scripts.financial_ai_review_orchestrator import run_specialist_reviews


class FinancialAiReviewOrchestratorTests(unittest.TestCase):
    def test_invokes_five_specialists_and_returns_advisory_result(self):
        calls = []
        def reviewer(request):
            calls.append(request["role"])
            return {"verdict": "approve", "summary": "Reviewed evidence.",
                    "findings": []}
        result = run_specialist_reviews(
            financial_files=["scripts/backtest_engine.py"],
            diff_by_file={"scripts/backtest_engine.py": "+run_backtest()"},
            reviewer=reviewer)
        self.assertEqual(len(calls), 5)
        self.assertIn("quant_backtest", calls)
        self.assertEqual(len(set(calls)), 5)
        self.assertEqual(result["overall_verdict"], "approve")
        self.assertFalse(result["merge_authorized"])

    def test_disagreement_never_becomes_approval(self):
        def reviewer(request):
            if request["role"] == "market_data":
                return {"verdict": "approve", "summary": "ok", "findings": []}
            return {"verdict": "uncertain", "summary": "missing evidence", "findings": []}
        result = run_specialist_reviews(
            financial_files=["scripts/market_data.py", "scripts/technical_indicators.py"],
            diff_by_file={"scripts/market_data.py": "+x", "scripts/technical_indicators.py": "+y"},
            reviewer=reviewer)
        self.assertEqual(result["overall_verdict"], "uncertain")
        self.assertTrue(result["conflicts_present"])

    def test_high_severity_finding_blocks_approval(self):
        def reviewer(request):
            return {"verdict": "approve", "summary": "reviewed",
                    "findings": [{"severity": "high", "path": request["files"][0],
                                  "explanation": "Evidence-backed issue."}]}
        result = run_specialist_reviews(
            financial_files=["scripts/backtest_engine.py"],
            diff_by_file={"scripts/backtest_engine.py": "+x"}, reviewer=reviewer)
        self.assertEqual(result["overall_verdict"], "request_changes")

    def test_rejects_finding_outside_assigned_files(self):
        def reviewer(request):
            return {"verdict": "request_changes", "summary": "issue",
                    "findings": [{"severity": "high", "path": "other.py",
                                  "explanation": "bad"}]}
        with self.assertRaisesRegex(ValueError, "unassigned file"):
            run_specialist_reviews(financial_files=["scripts/backtest_engine.py"],
                                   diff_by_file={"scripts/backtest_engine.py": "+x"},
                                   reviewer=reviewer)

    def test_rejects_untrusted_invalid_response(self):
        for response in (None, {"verdict": "approve"}, {"verdict": "approved", "summary": "x", "findings": []}):
            with self.subTest(response=response):
                with self.assertRaises(ValueError):
                    run_specialist_reviews(
                        financial_files=["scripts/backtest_engine.py"],
                        diff_by_file={"scripts/backtest_engine.py": "+x"},
                        reviewer=lambda _: response)

    def test_generic_files_do_not_call_specialists(self):
        def reviewer(_):
            raise AssertionError("should not be called")
        result = run_specialist_reviews(financial_files=["docs/readme.md"],
                                        diff_by_file={"docs/readme.md": "+x"},
                                        reviewer=reviewer)
        self.assertEqual(result["specialist_reviews"], [])
        self.assertEqual(result["overall_verdict"], "uncertain")


if __name__ == "__main__":
    unittest.main()
