"""Offline tests: no caller-provided value can certify review evidence."""
import unittest
from unittest.mock import patch

from scripts.pr_merge_candidate_gate import assess_candidate


class CompositeCandidateTests(unittest.TestCase):
    def run_gate(self, readiness, evidence):
        with patch("scripts.pr_merge_candidate_gate.assess_readiness",
                   return_value=readiness):
            return assess_candidate({}, [], [], protected=True,
                                    evidence_decision=evidence)

    def test_even_claimed_trusted_controller_is_not_authentication(self):
        self.assertEqual(self.run_gate(
            ("candidate", "ok"),
            ("candidate", "trusted-controller-verified"))[0], "manual")

    def test_readiness_failure_blocks(self):
        self.assertEqual(self.run_gate(
            ("manual", "stale CI"),
            ("candidate", "trusted-controller-verified"))[0], "manual")

    def test_untrusted_model_claims_do_not_satisfy_gate(self):
        for value in (None, True, "approve", "candidate",
                      {"verdict": "approve", "evidence_authenticated": True},
                      ("candidate", "model-approved"),
                      ("manual", "trusted-controller-verified")):
            with self.subTest(value=value):
                self.assertEqual(self.run_gate(("candidate", "ok"), value)[0],
                                 "manual")


if __name__ == "__main__":
    unittest.main()
