import unittest
from scripts.github_check_evidence import normalize_workflow_runs

SHA = "a" * 40
NAMES = frozenset({"Python input tests", "Merge policy"})


def runs():
    return [{"id": i + 1, "name": name, "head_sha": SHA,
             "event": "pull_request", "status": "completed", "conclusion": "success"}
            for i, name in enumerate(sorted(NAMES))]


class GithubCheckEvidenceTests(unittest.TestCase):
    def test_normalizes_exact_current_runs(self):
        self.assertEqual(len(normalize_workflow_runs(runs(), SHA, NAMES)), 2)

    def test_rejects_stale_missing_duplicate_failed_or_other_event(self):
        for change in ("stale", "missing", "duplicate", "failed", "event"):
            data = runs()
            if change == "stale":
                data[0]["head_sha"] = "b" * 40
            elif change == "missing":
                data.pop()
            elif change == "duplicate":
                data.append(dict(data[0], id=999))
            elif change == "failed":
                data[0]["conclusion"] = "failure"
            else:
                data[0]["event"] = "workflow_dispatch"
            with self.subTest(change=change):
                with self.assertRaises(ValueError):
                    normalize_workflow_runs(data, SHA, NAMES)


if __name__ == "__main__":
    unittest.main()
