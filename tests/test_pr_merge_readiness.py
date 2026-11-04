import unittest
from scripts.pr_merge_readiness import assess

SHA = "a" * 40
PR = {"base": "main", "state": "open", "draft": False,
      "mergeable": True, "head_sha": SHA, "changed_files": 1}
FILES = [{"filename": "docs/guide.md", "status": "modified",
          "additions": 2, "deletions": 1}]
CHECKS = [{"name": name, "head_sha": SHA, "status": "completed",
           "conclusion": "success"} for name in ("unit-tests", "merge-policy")]


class MergeReadinessTests(unittest.TestCase):
    def check(self, pr=None, files=None, checks=None, protected=True):
        return assess(PR if pr is None else pr,
                      FILES if files is None else files,
                      CHECKS if checks is None else checks,
                      protected=protected)[0]

    def test_candidate_requires_all_conditions(self):
        self.assertEqual(self.check(), "candidate")

    def test_protection_is_mandatory(self):
        self.assertEqual(self.check(protected=False), "manual")

    def test_draft_wrong_base_or_mergeability_rejected(self):
        for changes in ({"draft": True}, {"base": "other"},
                        {"mergeable": None}, {"state": "closed"},
                        {"head_sha": "not-a-sha"}):
            with self.subTest(changes=changes):
                self.assertEqual(self.check(pr={**PR, **changes}), "manual")

    def test_missing_failed_stale_and_duplicate_checks_rejected(self):
        for checks in ([], CHECKS[:1],
                       [CHECKS[0], {**CHECKS[1], "conclusion": "failure"}],
                       [CHECKS[0], {**CHECKS[1], "head_sha": "b" * 40}],
                       CHECKS + [CHECKS[0]],
                       CHECKS + [{"name": ["unit-tests"]}]):
            with self.subTest(checks=checks):
                self.assertEqual(self.check(checks=checks), "manual")

    def test_missing_file_count_and_other_failed_ci_rejected(self):
        for count in (None, True, "1", 0):
            with self.subTest(count=count):
                self.assertEqual(self.check(pr={**PR, "changed_files": count}), "manual")
        failed_extra = {"name": "security-scan", "head_sha": SHA,
                        "status": "completed", "conclusion": "failure"}
        self.assertEqual(self.check(checks=CHECKS + [failed_extra]), "manual")

    def test_sensitive_and_incomplete_file_lists_rejected(self):
        self.assertEqual(self.check(files=[{**FILES[0], "filename": "scripts/analysis.py"}]), "manual")
        self.assertEqual(self.check(pr={**PR, "changed_files": 2}), "manual")


if __name__ == "__main__":
    unittest.main()
