import unittest
from scripts.merge_safety_report import report


class MergeSafetyReportTests(unittest.TestCase):
    def test_missing_data_is_blocked(self):
        result = report({})
        self.assertFalse(result["ready"])
        self.assertEqual(result["decision"], "manual")
        self.assertTrue(result["blockers"])

    def test_untrusted_claim_cannot_enable_merge(self):
        result = report({"rulesets": [{"name": "protected"}],
                         "protected": True,
                         "pr": {"base": "main", "state": "open", "draft": False}})
        self.assertFalse(result["ready"])
        self.assertTrue(any("ruleset" in item for item in result["blockers"]))

    def test_invalid_payload_fails_closed(self):
        for payload in (None, [], "yes", 123):
            with self.subTest(payload=payload):
                self.assertEqual(report(payload)["decision"], "manual")

    def test_empty_rulesets_and_no_pr_are_explained(self):
        result = report({"rulesets": [], "pr": None, "files": [], "checks": []})
        self.assertGreaterEqual(len(result["blockers"]), 2)


if __name__ == "__main__":
    unittest.main()
