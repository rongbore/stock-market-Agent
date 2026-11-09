import json
from pathlib import Path, PurePosixPath
import tempfile
import unittest

from scripts.batch_research_plan import build_batch_plan, main


class BatchResearchPlanTests(unittest.TestCase):
    def test_plan_is_deterministic_and_preserves_unexecuted_status(self):
        symbols = ["600519.SS", "000776.SZ"]
        result = build_batch_plan(symbols, "2026-11-08")
        self.assertEqual(result, build_batch_plan(list(reversed(symbols)), "2026-11-08"))
        self.assertEqual(symbols, ["600519.SS", "000776.SZ"])
        self.assertEqual(result["status"], "PLANNED_ONLY")
        self.assertEqual(result["jobs_executed"], 0)
        self.assertFalse(result["execution_authorized"])
        self.assertEqual(len({job["job_id"] for job in result["jobs"]}), 2)
        self.assertTrue(all(job["status"] == "PENDING_INPUTS" for job in result["jobs"]))
        self.assertFalse(any(job["source_verified"] for job in result["jobs"]))

    def test_safe_relative_artifact_paths_and_date_separation(self):
        one = build_batch_plan(["000776.SZ"], "2026-11-08")
        two = build_batch_plan(["000776.SZ"], "2026-11-09")
        self.assertNotEqual(one["plan_id"], two["plan_id"])
        self.assertNotEqual(one["jobs"][0]["job_id"], two["jobs"][0]["job_id"])
        path = PurePosixPath(one["jobs"][0]["output_relative_path"])
        self.assertFalse(path.is_absolute())
        self.assertNotIn("..", path.parts)
        self.assertEqual(len(path.parts), 2)

    def test_rejects_duplicate_invalid_and_unbounded_symbols(self):
        for symbols in ([], "000776.SZ", ["000776.SZ"] * 2,
                        [f"{n:06d}.SZ" for n in range(101)],
                        ["../../secret"], ["000776.SZ/../../x"], [True], ["NVDA"], ["000776.sz"]):
            with self.subTest(symbols=symbols), self.assertRaises(ValueError):
                build_batch_plan(symbols, "2026-11-08")
        self.assertEqual(build_batch_plan([f"{n:06d}.SZ" for n in range(100)], "2026-11-08")["job_count"], 100)

    def test_rejects_noncanonical_or_invalid_dates(self):
        for day in (None, True, "20261108", "2026-02-30", "2026-11-08T00:00:00Z"):
            with self.subTest(day=day), self.assertRaises(ValueError):
                build_batch_plan(["000776.SZ"], day)

    def test_cli_writes_only_plan_and_invalid_input_preserves_existing_file(self):
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "batch.json"
            args = ["--symbols", "000776.SZ", "600519.SS", "--analysis-date", "2026-11-08",
                    "--output", str(output)]
            self.assertEqual(main(args), 0)
            original = output.read_bytes()
            self.assertEqual(json.loads(original)["job_count"], 2)
            self.assertEqual([p.name for p in Path(directory).iterdir()], ["batch.json"])
            with self.assertRaises(ValueError):
                main(["--symbols", "../x", "--analysis-date", "2026-11-08", "--output", str(output)])
            self.assertEqual(output.read_bytes(), original)

    def test_cli_rejects_symlink_output(self):
        with tempfile.TemporaryDirectory() as directory:
            target = Path(directory) / "target.json"
            target.write_text("preserve")
            link = Path(directory) / "link.json"
            link.symlink_to(target)
            with self.assertRaisesRegex(ValueError, "symbolic link"):
                main(["--symbols", "000776.SZ", "--analysis-date", "2026-11-08", "--output", str(link)])
            self.assertEqual(target.read_text(), "preserve")
