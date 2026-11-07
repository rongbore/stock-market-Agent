import io
import json
import unittest
from scripts.github_workflow_fetch import fetch_workflow_evidence

SHA = "a" * 40
REQUIRED = frozenset({"Python input tests"})


class Response:
    def __init__(self, data):
        self.data = io.BytesIO(json.dumps(data).encode())

    def __enter__(self):
        return self.data

    def __exit__(self, *args):
        self.data.close()


def run(event="pull_request", sha=SHA):
    return {"id": 42, "name": "Python input tests", "head_sha": sha,
            "event": event, "status": "completed", "conclusion": "success"}


class GitHubWorkflowFetchTests(unittest.TestCase):
    def test_reads_only_current_successful_run(self):
        calls = []
        def opener(req, timeout):
            calls.append((req.full_url, req.get_header("Authorization"), timeout))
            return Response({"total_count": 1, "workflow_runs": [run()]})
        result = fetch_workflow_evidence("owner/repo", SHA, REQUIRED,
                                         token="test-token", opener=opener)
        self.assertEqual(result[0]["head_sha"], SHA)
        self.assertIn("head_sha=" + SHA, calls[0][0])
        self.assertEqual(calls[0][1], "Bearer test-token")

    def test_rejects_stale_or_non_pr_run(self):
        for bad in (run(sha="b" * 40), run(event="workflow_dispatch")):
            with self.subTest(bad=bad):
                with self.assertRaises(ValueError):
                    fetch_workflow_evidence("owner/repo", SHA, REQUIRED,
                        token="test-token", opener=lambda req, timeout: Response(
                            {"total_count": 1, "workflow_runs": [bad]}))


    def test_rejects_truncated_response_and_wrong_count(self):
        for payload in (
            {"total_count": 1, "workflow_runs": []},
            {"total_count": 0, "workflow_runs": [run()]},
            {"workflow_runs": [run()]},
            {"total_count": True, "workflow_runs": [run()]},
        ):
            with self.subTest(payload=payload):
                with self.assertRaises(ValueError):
                    fetch_workflow_evidence("owner/repo", SHA, REQUIRED,
                        token="test-token", opener=lambda req, timeout: Response(payload))

    def test_rejects_oversized_body(self):
        class HugeResponse:
            def __enter__(self):
                return io.BytesIO(b"x" * 2_000_001)

            def __exit__(self, *args):
                return False

        with self.assertRaises(ValueError):
            fetch_workflow_evidence("owner/repo", SHA, REQUIRED,
                token="test-token", opener=lambda req, timeout: HugeResponse())

    def test_rejects_unsafe_repository_and_token(self):
        for repo, token in (
            ("owner/../repo", "test-token"),
            ("owner/repo", "bad\\ntoken"),
            ("owner/repo", "  "),
        ):
            with self.subTest(repo=repo):
                with self.assertRaises(ValueError):
                    fetch_workflow_evidence(repo, SHA, REQUIRED, token=token)

    def test_rejects_ambiguous_pagination_and_missing_token(self):
        with self.assertRaises(ValueError):
            fetch_workflow_evidence("owner/repo", SHA, REQUIRED, token="")
        with self.assertRaises(ValueError):
            fetch_workflow_evidence("owner/repo", SHA, REQUIRED, token="test-token",
                opener=lambda req, timeout: Response(
                    {"total_count": 101, "workflow_runs": [run()]}))


if __name__ == "__main__":
    unittest.main()
