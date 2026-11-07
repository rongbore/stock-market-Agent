"""Strict integer boundary regressions for review artifact provenance."""
import unittest

from scripts.github_review_artifact_preflight import assess_provenance


class StrictWorkflowIdsTests(unittest.TestCase):
    def test_boolean_workflow_id_cannot_match_integer_one(self):
        run = dict(repository_full_name="rongbore/stock-market-Agent",
                   head_sha="a" * 40, workflow_id=True, event="pull_request",
                   path=".github/workflows/ai-pr-review-manual.yml",
                   head_repository_full_name="rongbore/stock-market-Agent", run_attempt=1,
                   status="completed", conclusion="success", id=1)
        artifact = dict(workflow_run_id=1, id=2, expired=False,
                        size_in_bytes=1024, name="ai-review-evidence")
        status, _ = assess_provenance(
            repo="rongbore/stock-market-Agent", expected_head_sha="a" * 40,
            expected_workflow_id=1,
            expected_workflow_path=".github/workflows/ai-pr-review-manual.yml",
            expected_event="pull_request", run=run, artifact=artifact)
        self.assertEqual(status, "manual")

    def test_boolean_artifact_run_id_cannot_match_integer_one(self):
        run = dict(repository_full_name="rongbore/stock-market-Agent",
                   head_sha="a" * 40, workflow_id=1, event="pull_request",
                   path=".github/workflows/ai-pr-review-manual.yml",
                   head_repository_full_name="rongbore/stock-market-Agent", run_attempt=1,
                   status="completed", conclusion="success", id=1)
        artifact = dict(workflow_run_id=True, id=2, expired=False,
                        size_in_bytes=1024, name="ai-review-evidence")
        status, _ = assess_provenance(
            repo="rongbore/stock-market-Agent", expected_head_sha="a" * 40,
            expected_workflow_id=1,
            expected_workflow_path=".github/workflows/ai-pr-review-manual.yml",
            expected_event="pull_request", run=run, artifact=artifact)
        self.assertEqual(status, "manual")

    def test_valid_integer_ids_remain_candidate_only(self):
        run = dict(repository_full_name="rongbore/stock-market-Agent",
                   head_sha="a" * 40, workflow_id=1, event="pull_request",
                   path=".github/workflows/ai-pr-review-manual.yml",
                   head_repository_full_name="rongbore/stock-market-Agent", run_attempt=1,
                   status="completed", conclusion="success", id=1)
        artifact = dict(workflow_run_id=1, id=2, expired=False,
                        size_in_bytes=1024, name="ai-review-evidence")
        status, _ = assess_provenance(
            repo="rongbore/stock-market-Agent", expected_head_sha="a" * 40,
            expected_workflow_id=1,
            expected_workflow_path=".github/workflows/ai-pr-review-manual.yml",
            expected_event="pull_request", run=run, artifact=artifact)
        self.assertEqual(status, "candidate")


if __name__ == "__main__":
    unittest.main()
