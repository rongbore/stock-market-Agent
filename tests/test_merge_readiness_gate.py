import unittest
from scripts.merge_readiness_gate import evaluate_readiness


SHA = "a" * 40


def evidence(tier="documentation_candidate"):
    return dict(
        tier_result={"tier": tier, "auto_merge_authorized": False},
        pr={"head_sha": SHA, "reviewed_head_sha": SHA, "draft": False,
            "state": "open", "base_ref": "main", "mergeable": True,
            "base_sha": "b" * 40,
            "base_repo_full_name": "rongbore/stock-market-Agent",
            "head_repo_full_name": "rongbore/stock-market-Agent"},
        checks=[{"id": i, "app_id": 9001, "name": n, "head_sha": SHA,
                 "status": "completed", "conclusion": "success"}
                for i, n in enumerate(("unit-tests", "merge-policy"), start=1)],
        review={"head_sha": SHA, "verdict": "approve", "trusted": True},
        review_threads=[],
        has_changes_requested_review=False,
        current_base_sha="b" * 40,
        checks_complete=True,
        expected_check_count=2,
        review_threads_complete=True,
        trusted_check_app_ids=[9001],
    )


class ReadinessTests(unittest.TestCase):
    def test_documentation_ready_is_not_authorization(self):
        result = evaluate_readiness(**evidence())
        self.assertEqual(result["decision"], "READY_FOR_TRUSTED_CONTROLLER")
        self.assertFalse(result["merge_authorized"])
        self.assertFalse(result["evidence_authenticated"])

    def test_tests_financial_and_security_tiers_are_rejected(self):
        for tier in ("tests_candidate", "financial_algorithm_requires_independent_validation",
                     "security_configuration_candidate"):
            with self.subTest(tier=tier):
                result = evaluate_readiness(**evidence(tier))
                self.assertEqual(result["decision"], "BLOCKED")
                self.assertIn("unapproved_change_tier", result["reasons"])

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

    def test_fork_pull_request_blocks(self):
        e = evidence()
        e["pr"]["head_repo_full_name"] = "contributor/stock-market-Agent"
        result = evaluate_readiness(**e)
        self.assertEqual(result["decision"], "BLOCKED")
        self.assertIn("fork_or_unverified_head_repository", result["reasons"])

    def test_missing_repository_identity_blocks(self):
        e = evidence()
        del e["pr"]["head_repo_full_name"]
        result = evaluate_readiness(**e)
        self.assertEqual(result["decision"], "BLOCKED")
        self.assertIn("fork_or_unverified_head_repository", result["reasons"])

    def test_stale_or_missing_base_sha_blocks(self):
        e = evidence()
        e["current_base_sha"] = "c" * 40
        result = evaluate_readiness(**e)
        self.assertEqual(result["decision"], "BLOCKED")
        self.assertIn("base_not_current_or_unverified", result["reasons"])
        e = evidence()
        del e["pr"]["base_sha"]
        result = evaluate_readiness(**e)
        self.assertEqual(result["decision"], "BLOCKED")
        self.assertIn("base_not_current_or_unverified", result["reasons"])

    def test_unresolved_review_thread_blocks(self):
        e = evidence()
        e["review_threads"] = [{"is_resolved": False}]
        result = evaluate_readiness(**e)
        self.assertEqual(result["decision"], "BLOCKED")
        self.assertIn("unresolved_review_threads", result["reasons"])

    def test_missing_or_malformed_review_thread_evidence_blocks(self):
        for threads in (None, [{"is_resolved": "false"}], [None]):
            with self.subTest(threads=threads):
                e = evidence()
                e["review_threads"] = threads
                result = evaluate_readiness(**e)
                self.assertEqual(result["decision"], "BLOCKED")

    def test_active_change_request_blocks(self):
        e = evidence()
        e["has_changes_requested_review"] = True
        result = evaluate_readiness(**e)
        self.assertEqual(result["decision"], "BLOCKED")
        self.assertIn("changes_requested_review", result["reasons"])

    def test_missing_change_request_state_blocks(self):
        e = evidence()
        e["has_changes_requested_review"] = None
        result = evaluate_readiness(**e)
        self.assertEqual(result["decision"], "BLOCKED")
        self.assertIn("review_status_missing_or_invalid", result["reasons"])

    def test_incomplete_check_pagination_blocks(self):
        e = evidence()
        e["checks_complete"] = False
        result = evaluate_readiness(**e)
        self.assertEqual(result["decision"], "BLOCKED")
        self.assertIn("check_evidence_incomplete_or_unverified", result["reasons"])
        e = evidence()
        e["expected_check_count"] = 3
        result = evaluate_readiness(**e)
        self.assertEqual(result["decision"], "BLOCKED")
        self.assertIn("check_count_mismatch", result["reasons"])

    def test_incomplete_review_thread_pagination_blocks(self):
        e = evidence()
        e["review_threads_complete"] = False
        result = evaluate_readiness(**e)
        self.assertEqual(result["decision"], "BLOCKED")
        self.assertIn("review_threads_incomplete_or_unverified", result["reasons"])

    def test_untrusted_or_missing_check_provenance_blocks(self):
        e = evidence()
        e["checks"][0]["app_id"] = 9002
        result = evaluate_readiness(**e)
        self.assertEqual(result["decision"], "BLOCKED")
        self.assertIn("check_provenance_missing_or_untrusted", result["reasons"])
        e = evidence()
        del e["checks"][0]["id"]
        result = evaluate_readiness(**e)
        self.assertEqual(result["decision"], "BLOCKED")
        self.assertIn("check_provenance_missing_or_untrusted", result["reasons"])

    def test_duplicate_check_run_ids_block(self):
        e = evidence()
        e["checks"][1]["id"] = e["checks"][0]["id"]
        result = evaluate_readiness(**e)
        self.assertEqual(result["decision"], "BLOCKED")
        self.assertIn("duplicate_check_run_id", result["reasons"])

    def test_missing_trusted_app_allowlist_blocks(self):
        e = evidence()
        e["trusted_check_app_ids"] = []
        result = evaluate_readiness(**e)
        self.assertEqual(result["decision"], "BLOCKED")
        self.assertIn("trusted_check_app_allowlist_invalid", result["reasons"])


if __name__ == "__main__":
    unittest.main()
