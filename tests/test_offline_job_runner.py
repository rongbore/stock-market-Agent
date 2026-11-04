import subprocess
import unittest
from types import SimpleNamespace

from scripts.offline_job_runner import run_job


class OfflineJobRunnerTests(unittest.TestCase):
    def test_success_first_attempt(self):
        result = run_job(["python", "--version"], runner=lambda *a, **k: SimpleNamespace(returncode=0))
        self.assertTrue(result["success"])
        self.assertEqual(len(result["attempts"]), 1)

    def test_retry_until_success(self):
        codes = iter([1, 2, 0])
        waits = []
        result = run_job(["offline-task"], runner=lambda *a, **k: SimpleNamespace(returncode=next(codes)),
                         sleep=waits.append, delay=2)
        self.assertTrue(result["success"])
        self.assertEqual(waits, [2, 4])
        self.assertEqual(len(result["attempts"]), 3)

    def test_exhausted_retries(self):
        result = run_job(["offline-task"], attempts=2, delay=0,
                         runner=lambda *a, **k: SimpleNamespace(returncode=3), sleep=lambda x: None)
        self.assertFalse(result["success"])
        self.assertEqual(len(result["attempts"]), 2)

    def test_timeout_and_launch_error(self):
        errors = iter([subprocess.TimeoutExpired("offline-task", 1), OSError("missing")])
        def runner(*args, **kwargs):
            raise next(errors)
        result = run_job(["offline-task"], attempts=2, delay=0, runner=runner, sleep=lambda x: None)
        self.assertEqual([x["status"] for x in result["attempts"]], ["timeout", "launch_error"])

    def test_invalid_limits(self):
        for opts in ({"attempts": 0}, {"attempts": 6}, {"timeout": 0},
                     {"delay": -1}, {"delay": 31}):
            with self.assertRaises(ValueError):
                run_job(["offline-task"], **opts)
        with self.assertRaises(ValueError):
            run_job([])
        with self.assertRaises(ValueError):
            run_job("offline-task")


if __name__ == "__main__":
    unittest.main()
