import unittest
from pathlib import Path


class DiagnosticWorkflowTests(unittest.TestCase):
    def test_manual_read_only_workflow(self):
        workflow = Path(".github/workflows/merge-protection-diagnostic.yml").read_text(
            encoding="utf-8"
        )
        self.assertIn("workflow_dispatch:", workflow)
        self.assertIn("contents: read", workflow)
        self.assertIn("github.ref == 'refs/heads/main'", workflow)
        self.assertIn("persist-credentials: false", workflow)
        self.assertIn("scripts.merge_safety_report --strict", workflow)
        self.assertNotIn("pull_request_target:", workflow)
        self.assertNotIn("contents: write", workflow)
        self.assertNotIn("gh pr merge", workflow)


if __name__ == "__main__":
    unittest.main()
