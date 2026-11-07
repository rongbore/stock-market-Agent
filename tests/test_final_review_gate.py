import unittest
from scripts.final_review_gate import evaluate, REQUIRED_CHECKS

SHA = "a" * 40


def evidence():
    return dict(head_sha=SHA, risk={"status": "CANDIDATE", "head_sha": SHA},
                ai_review={"status": "PASS", "head_sha": SHA, "review_complete": True},
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
            {"ai_review": {"status": "PASS", "head_sha": "b" * 40, "review_complete": True}},
            {"checks": []},
        ]
        for change in cases:
            data = evidence()
            data.update(change)
            with self.subTest(change=change):
                self.assertEqual(evaluate(**data)["decision"], "BLOCKED")

    def test_failed_check_blocks(self):
        data = evidence()
        data["checks"][0]["conclusion"] = "failure"
        self.assertEqual(evaluate(**data)["decision"], "BLOCKED")


if __name__ == "__main__":
    unittest.main()
