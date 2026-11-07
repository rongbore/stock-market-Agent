import unittest
from scripts.merge_readiness_gate import evaluate_readiness


SHA = "a" * 40


def evidence(tier="documentation_candidate"):
    return dict(
        tier_result={"tier": tier, "auto_merge_authorized": False},
        pr={"head_sha": SHA, "reviewed_head_sha": SHA, "draft": False,
            "state": "open", "base_ref": "main", "mergeable": True},
        checks=[{"name": n, "head_sha": SHA, "status": "completed", "conclusion": "success"}
                for n in ("unit-tests", "merge-policy")],
        review={"head_sha": SHA, "verdict": "approve", "trusted": True},
    )


class ReadinessTests(unittest.TestCase):
    def test_documentation_ready_is_not_authorization(self):
        result = evaluate_readiness(**evidence())
        self.assertEqual(result["decision"], "READY_FOR_TRUSTED_CONTROLLER")
        self.assertFalse(result["merge_authorized"])
        self.assertFalse(result["evidence_authenticated"])

    def test_tests_tier(self):
        self.assertEqual(evaluate_readiness(**evidence("tests_candidate"))["decision"], "READY_FOR_TRUSTED_CONTROLLER")

    def test_financial_needs_independent_validation(self):
        result = evaluate_readiness(**evidence("financial_algorithm_requires_independent_validation"))
        self.assertIn("independent_financial_validation_missing", result["reasons"])

    def test_financial_passed_independent_validation(self):
        e = evidence("financial_algorithm_requires_independent_validation")
        e["independent_validation"] = {"head_sha": SHA, "passed": True, "trusted": True}
        self.assertEqual(evaluate_readiness(**e)["decision"], "READY_FOR_TRUSTED_CONTROLLER")

    def test_stale_review_blocks(self):
        e = evidence()
        e["review"]["head_sha"] = "b" * 40
        self.assertEqual(evaluate_readiness(**e)["decision"], "BLOCKED")

    def test_pending_check_blocks(self):
        e = evidence()
        e["checks"][0]["status"] = "in_progress"
        self.assertIn("stale_pending_or_failed_check", evaluate_readiness(**e)["reasons"])

    def test_draft_blocks(self):
        e = evidence()
        e["pr"]["draft"] = True
        self.assertEqual(evaluate_readiness(**e)["decision"], "BLOCKED")

    def test_duplicate_check_blocks(self):
        e = evidence()
        e["checks"].append(dict(e["checks"][0]))
        self.assertIn("duplicate_check", evaluate_readiness(**e)["reasons"])

    def test_unlisted_tier_blocks(self):
        e = evidence("manual")
        self.assertEqual(evaluate_readiness(**e)["decision"], "BLOCKED")

    def test_wrong_base_blocks(self):
        e = evidence()
        e["pr"]["base_ref"] = "development"
        self.assertEqual(evaluate_readiness(**e)["decision"], "BLOCKED")


if __name__ == "__main__":
    unittest.main()
