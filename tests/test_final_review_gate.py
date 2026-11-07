import unittest
from scripts.final_review_gate import evaluate, REQUIRED_CHECKS

SHA = "a" * 40


def evidence():
    return dict(head_sha=SHA, risk={"status": "CANDIDATE", "head_sha": SHA},
                ai_review={"verdict": "PASS", "head_sha": SHA, "review_complete": True,
                           "findings": [], "policy_version": "1"},
                checks=[{"name": name, "head_sha": SHA, "status": "completed",
                         "conclusion": "success"} for name in sorted(REQUIRED_CHECKS)],
                is_draft=False, changed_paths=["docs/guide.md"])


class FinalReviewGateTests(unittest.TestCase):
    def test_clean_inputs_still_do_not_authorize_merge(self):
        result = evaluate(**evidence())
        self.assertEqual(result["decision"], "ELIGIBLE_FOR_POLICY_REVIEW")
        self.assertFalse(result["merge_authorized"])

    def test_fail_closed(self):
        cases = [
            {"is_draft": True},
            {"changed_paths": [".github/workflows/ci.yml"]},
            {"risk": {"status": "BLOCKED", "head_sha": SHA}},
            {"ai_review": {"verdict": "PASS", "head_sha": "b" * 40, "review_complete": True,
                           "findings": [], "policy_version": "1"}},
            {"checks": []},
        ]
        for change in cases:
            data = evidence()
            data.update(change)
            with self.subTest(change=change):
                self.assertEqual(evaluate(**data)["decision"], "BLOCKED")


    def test_forged_pass_status_without_valid_contract_blocks(self):
        data = evidence()
        data["ai_review"] = {"status": "PASS", "head_sha": SHA, "review_complete": True}
        self.assertEqual(evaluate(**data)["decision"], "BLOCKED")

    def test_pass_with_findings_or_missing_policy_blocks(self):
        for review in (
            {"verdict": "PASS", "head_sha": SHA, "review_complete": True,
             "findings": [{"severity": "high", "message": "Unsafe"}], "policy_version": "1"},
            {"verdict": "PASS", "head_sha": SHA, "review_complete": True, "findings": []},
        ):
            data = evidence()
            data["ai_review"] = review
            with self.subTest(review=review):
                self.assertEqual(evaluate(**data)["decision"], "BLOCKED")


    def test_workflow_run_evidence_matches_normalized_checks(self):
        data = evidence()
        data["workflow_runs"] = [
            {"id": i + 1, "name": c["name"], "head_sha": SHA,
             "event": "pull_request", "status": "completed",
             "conclusion": "success"}
            for i, c in enumerate(data["checks"])
        ]
        self.assertEqual(evaluate(**data)["decision"], "ELIGIBLE_FOR_POLICY_REVIEW")
        self.assertFalse(evaluate(**data)["merge_authorized"])

        data["workflow_runs"][0]["head_sha"] = "b" * 40
        self.assertEqual(evaluate(**data)["decision"], "BLOCKED")

    def test_workflow_run_duplicate_and_forged_checks_block(self):
        data = evidence()
        data["workflow_runs"] = [
            {"id": i + 1, "name": c["name"], "head_sha": SHA,
             "event": "pull_request", "status": "completed",
             "conclusion": "success"}
            for i, c in enumerate(data["checks"])
        ]
        data["workflow_runs"].append(dict(data["workflow_runs"][0], id=999))
        self.assertEqual(evaluate(**data)["decision"], "BLOCKED")
        data["workflow_runs"].pop()
        data["checks"][0]["status"] = "queued"
        self.assertEqual(evaluate(**data)["decision"], "BLOCKED")

    def test_failed_check_blocks(self):
        data = evidence()
        data["checks"][0]["conclusion"] = "failure"
        self.assertEqual(evaluate(**data)["decision"], "BLOCKED")


if __name__ == "__main__":
    unittest.main()
