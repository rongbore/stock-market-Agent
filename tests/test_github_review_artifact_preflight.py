"""Negative tests for GitHub review artifact provenance preflight."""
import unittest
from scripts.github_review_artifact_preflight import assess_provenance

SHA = "a" * 40
REPO = "rongbore/stock-market-Agent"


def run():
    return dict(repository_full_name=REPO, head_sha=SHA, workflow_id=42,
                event="pull_request", status="completed", conclusion="success", id=100)


def artifact():
    return dict(workflow_run_id=100, id=101, expired=False,
                size_in_bytes=1024, name="ai-review-evidence")


def assess(r=None, a=None, **kw):
    args = dict(repo=REPO, expected_head_sha=SHA, expected_workflow_id=42,
                run=run() if r is None else r,
                artifact=artifact() if a is None else a)
    args.update(kw)
    return assess_provenance(**args)[0]


class ProvenancePreflightTests(unittest.TestCase):
    def test_matching_metadata_only_candidate(self):
        self.assertEqual(assess(), "candidate")

    def test_wrong_repo_sha_or_workflow_blocks(self):
        for field, value in (("repository_full_name", "attacker/repo"),
                             ("head_sha", "b" * 40), ("workflow_id", 43),
                             ("status", "in_progress"), ("conclusion", "failure"),
                             ("event", "push"), ("id", 0)):
            with self.subTest(field=field):
                r = run()
                r[field] = value
                self.assertEqual(assess(r=r), "manual")

    def test_wrong_artifact_or_expiry_blocks(self):
        for field, value in (("workflow_run_id", 999), ("id", 0),
                             ("expired", True), ("expired", None),
                             ("size_in_bytes", 0), ("size_in_bytes", 1048577),
                             ("name", "arbitrary-report")):
            with self.subTest(field=field):
                a = artifact()
                a[field] = value
                self.assertEqual(assess(a=a), "manual")

    def test_missing_or_malformed_metadata_blocks(self):
        self.assertEqual(assess(r={}), "manual")
        self.assertEqual(assess(a={}), "manual")
        self.assertEqual(assess(repo="attacker/repo"), "manual")
        self.assertEqual(assess(expected_head_sha="bad"), "manual")
        self.assertEqual(assess(expected_workflow_id=True), "manual")


if __name__ == "__main__":
    unittest.main()
