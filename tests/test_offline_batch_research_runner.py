from copy import deepcopy
import json
from pathlib import Path
import tempfile
import unittest

from scripts.batch_research_plan import build_batch_plan
from scripts.offline_batch_research_runner import run_batch_plan, main


def report(symbol="000776.SZ", **changes):
    result = {"symbol": symbol, "dates": ["2026-11-05", "2026-11-06"], "prices": [10.0, 11.0]}
    return {**result, **changes}


class OfflineBatchRunnerTests(unittest.TestCase):
    def setUp(self):
        self.plan = build_batch_plan(["000776.SZ", "600519.SS"], "2026-11-08")

    def test_mixed_success_and_failure_are_isolated_and_counted(self):
        result = run_batch_plan(self.plan, {"000776.SZ": report(), "600519.SS": report("wrong")})
        self.assertEqual((result["job_count"], result["succeeded_count"], result["failed_count"]), (2, 1, 1))
        self.assertEqual(result["status"], "COMPLETED_WITH_FAILURES")
        self.assertFalse(result["results"][0]["brief"]["source_verified"])
        self.assertEqual(result["results"][1]["status"], "FAILED_INPUT_VALIDATION")
        self.assertIsNone(result["results"][1]["brief"])

    def test_missing_input_is_not_reported_as_success(self):
        result = run_batch_plan(self.plan, {"000776.SZ": report()})
        self.assertEqual(result["failed_count"], 1)
        self.assertEqual(result["results"][1]["status"], "MISSING_INPUT")

    def test_invalid_dates_and_nonfinite_prices_fail_per_job(self):
        changes = [{"dates": ["2026-11-09"], "prices": [1]},
                   {"dates": ["20261106"], "prices": [1]},
                   {"dates": ["2026-02-30"], "prices": [1]},
                   {"dates": [1], "prices": [1]},
                   {"dates": ["2026-11-06", "2026-11-05"]},
                   {"dates": ["2026-11-06", "2026-11-06"]},
                   {"prices": [10, float("nan")]}, {"prices": [True, 1]},
                   {"prices": [1e-308, 1e308]}]
        for change in changes:
            with self.subTest(change=change):
                result = run_batch_plan(self.plan, {"000776.SZ": report(**change),
                                                    "600519.SS": report("600519.SS")})
                self.assertEqual(result["results"][0]["status"], "FAILED_INPUT_VALIDATION")
                self.assertEqual(result["succeeded_count"], 1)

    def test_tampered_plan_rejected_before_any_job_runs(self):
        for field, value in (("operation", "shell"), ("output_relative_path", "../../x"),
                             ("status", "COMPLETED")):
            changed = deepcopy(self.plan)
            changed["jobs"][0][field] = value
            with self.subTest(field=field), self.assertRaisesRegex(ValueError, "contract"):
                run_batch_plan(changed, {"000776.SZ": report()})
        changed = deepcopy(self.plan)
        changed["job_count"] = True
        with self.assertRaises(ValueError):
            run_batch_plan(changed, {})

    def test_unknown_report_symbol_rejected(self):
        with self.assertRaises(ValueError):
            run_batch_plan(self.plan, {"../../x": report()})

    def test_cli_outputs_only_one_bundle_and_preserves_inputs(self):
        with tempfile.TemporaryDirectory() as directory:
            directory = Path(directory)
            plan_file, reports_file, output = [directory / name for name in ("plan.json", "reports.json", "bundle.json")]
            plan_file.write_text(json.dumps(self.plan))
            reports_file.write_text(json.dumps({"000776.SZ": report(), "600519.SS": report("600519.SS")}))
            args = ["--plan", str(plan_file), "--reports", str(reports_file), "--output", str(output)]
            self.assertEqual(main(args), 0)
            self.assertEqual(json.loads(output.read_text())["status"], "COMPLETED_UNVERIFIED")
            self.assertEqual(sorted(p.name for p in directory.iterdir()), ["bundle.json", "plan.json", "reports.json"])
            original = plan_file.read_bytes()
            with self.assertRaises(ValueError):
                main(args[:-1] + [str(plan_file)])
            self.assertEqual(plan_file.read_bytes(), original)
