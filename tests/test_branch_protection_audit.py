import unittest
from scripts.branch_protection_audit import audit_legacy_protection, audit_repository_state


class ProtectionAuditTests(unittest.TestCase):
    def test_unavailable_or_empty_rulesets_fail_closed(self):
        for rulesets in (None, [], {}, "enabled"):
            with self.subTest(rulesets=rulesets):
                self.assertFalse(audit_repository_state(rulesets, None)[0])

    def test_summary_rulesets_do_not_prove_enforcement(self):
        self.assertFalse(audit_repository_state([{"name": "main protection"}], {})[0])

    def test_unavailable_legacy_protection_fails_closed(self):
        for data in (None, {}, "403", []):
            with self.subTest(data=data):
                self.assertFalse(audit_legacy_protection(data)[0])

    def test_even_plausible_legacy_settings_need_effective_audit(self):
        data = {
            "required_status_checks": {"strict": True, "contexts": ["unit-tests", "merge-policy"]},
            "enforce_admins": {"enabled": True},
            "allow_force_pushes": {"enabled": False},
            "allow_deletions": {"enabled": False},
            "required_pull_request_reviews": {"required_approving_review_count": 1},
        }
        self.assertFalse(audit_legacy_protection(data)[0])


if __name__ == "__main__":
    unittest.main()
