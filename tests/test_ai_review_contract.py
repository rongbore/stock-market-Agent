import unittest
from scripts.ai_review_contract import validate_review

SHA = "a" * 40


def sample(**kwargs):
    obj = {"head_sha": SHA, "verdict": "PASS", "findings": [],
           "review_complete": True, "policy_version": "1"}
    obj.update(kwargs)
    return obj


class AIReviewContractTests(unittest.TestCase):
    def test_valid_pass_is_not_merge_authorization(self):
        result = validate_review(sample(), SHA)
        self.assertEqual(result["status"], "PASS")
        self.assertFalse(result["merge_authorized"])

    def test_stale_sha_blocks(self):
        self.assertEqual(validate_review(sample(head_sha="b" * 40), SHA)["status"], "BLOCKED")

    def test_missing_or_malformed_blocks(self):
        for obj in (None, {}, sample(verdict="APPROVED"), sample(review_complete=False),
                    sample(findings=[{"severity": "high", "message": "risk"}]),
                    sample(policy_version="2"), sample(findings="none")):
            with self.subTest(obj=obj):
                self.assertEqual(validate_review(obj, SHA)["status"], "BLOCKED")

    def test_changes_required_not_pass(self):
        result = validate_review(sample(verdict="CHANGES_REQUIRED",
                                        findings=[{"severity": "medium", "message": "Needs tests"}]), SHA)
        self.assertEqual(result["status"], "CHANGES_REQUIRED")


if __name__ == "__main__":
    unittest.main()
