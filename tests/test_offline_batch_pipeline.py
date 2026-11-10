from copy import deepcopy
from contextlib import redirect_stderr
import hashlib
import io
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from scripts.offline_batch_pipeline import build_pipeline, main
from scripts.offline_batch_research_runner import _canonical_json_bytes, MAX_INPUT_BYTES

ROOT = Path(__file__).resolve().parents[1]
EXAMPLE = ROOT / "examples/batch_research/SYNTHETIC_offline_pipeline.json"


class OfflinePipelineTests(unittest.TestCase):
    def config(self):
        return json.loads(EXAMPLE.read_text())

    def test_deterministic_stages_hashes_and_no_input_mutation(self):
        config = self.config()
        original = deepcopy(config)
        result = build_pipeline(config)
        self.assertEqual(result, build_pipeline(deepcopy(config)))
        self.assertEqual(config, original)
        payload = {key: value for key, value in result.items() if key != "artifact_payload_sha256"}
        self.assertEqual(result["artifact_payload_sha256"], hashlib.sha256(_canonical_json_bytes(payload)).hexdigest())
        self.assertEqual(result["pipeline_input_sha256"], hashlib.sha256(_canonical_json_bytes(config)).hexdigest())
        self.assertEqual(result["bundle"]["plan_sha256"], hashlib.sha256(_canonical_json_bytes(result["plan"])).hexdigest())
        changed = deepcopy(config)
        changed["reports"]["000776.SZ"]["prices"][-1] = 12.0
        self.assertNotEqual(result["artifact_payload_sha256"], build_pipeline(changed)["artifact_payload_sha256"])
        self.assertFalse(result["source_verified"])
        self.assertFalse(result["historical_point_in_time_verified"])

    def test_mixed_valid_invalid_and_missing_reports_use_existing_stages(self):
        result = build_pipeline(self.config())
        self.assertEqual(result["bundle"]["succeeded_count"], 1)
        self.assertEqual(result["bundle"]["failed_count"], 2)
        self.assertEqual([row["status"] for row in result["bundle"]["results"]],
                         ["MISSING_INPUT", "COMPLETED_UNVERIFIED", "FAILED_INPUT_VALIDATION"])
        self.assertIn("合成测试数据；不是实际市场数据", result["summary_markdown"])
        self.assertIn("未提供趋势报告", result["summary_markdown"])
        self.assertIn("股票代码、日期或价格校验失败", result["summary_markdown"])

    def test_true_cli_end_to_end_reproducible_and_single_artifact(self):
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "result.json"
            args = [sys.executable, "-m", "scripts.offline_batch_pipeline", "--input", str(EXAMPLE),
                    "--output", str(output), "--max-rows", "2"]
            completed = subprocess.run(args, cwd=ROOT, capture_output=True, text=True)
            self.assertEqual(completed.returncode, 0, completed.stderr)
            original = output.read_bytes()
            artifact = json.loads(original)
            self.assertIn("plan", artifact)
            self.assertIn("bundle", artifact)
            self.assertIn("显示 2 项，省略 1 项", artifact["summary_markdown"])
            self.assertEqual(subprocess.run(args, cwd=ROOT, capture_output=True).returncode, 0)
            self.assertEqual(output.read_bytes(), original)
            self.assertEqual([p.name for p in Path(directory).iterdir()], ["result.json"])

    def test_invalid_config_and_args_leave_existing_output_intact(self):
        with tempfile.TemporaryDirectory() as directory:
            source, output = Path(directory) / "input.json", Path(directory) / "output.json"
            output.write_text("preserve")
            args = ["--input", str(source), "--output", str(output)]
            bad = self.config()
            bad["untrusted_command"] = "run"
            source.write_text(json.dumps(bad))
            with self.assertRaises(ValueError):
                main(args)
            self.assertEqual(output.read_text(), "preserve")
            source.write_text(EXAMPLE.read_text())
            with self.assertRaises(ValueError):
                main(args + ["--max-rows", "0"])
            self.assertEqual(output.read_text(), "preserve")
            with self.assertRaises(ValueError):
                main(args[:-1] + [str(source)])
            self.assertEqual(json.loads(source.read_text()), self.config())
            with redirect_stderr(io.StringIO()), self.assertRaises(SystemExit):
                main(["--input", str(source)])
            self.assertEqual(output.read_text(), "preserve")

    def test_rejects_missing_unknown_duplicate_nonfinite_and_oversized_structures(self):
        config = self.config()
        del config["data_kind"]
        with self.assertRaises(ValueError):
            build_pipeline(config)
        config = self.config()
        config["data_kind"] = "VERIFIED"
        with self.assertRaises(ValueError):
            build_pipeline(config)
        for extra in (float("nan"), "x" * 3500000):
            config = self.config()
            config["reports"]["000776.SZ"]["extra"] = extra
            with self.assertRaises(ValueError):
                build_pipeline(config)
        with tempfile.TemporaryDirectory() as directory:
            source, output = Path(directory) / "in.json", Path(directory) / "out.json"
            source.write_text('{"schema_version":"0.1","schema_version":"wrong"}')
            with self.assertRaises(ValueError):
                main(["--input", str(source), "--output", str(output)])
            self.assertFalse(output.exists())

    def test_oversized_file_is_rejected_before_output_replacement(self):
        with tempfile.TemporaryDirectory() as directory:
            source, output = Path(directory) / "input.json", Path(directory) / "artifact.json"
            source.write_bytes(b" " * (MAX_INPUT_BYTES + 1))
            output.write_text("preserve")
            with self.assertRaisesRegex(ValueError, "too large"):
                main(["--input", str(source), "--output", str(output)])
            self.assertEqual(output.read_text(), "preserve")

    def test_cli_refuses_symlink_output(self):
        with tempfile.TemporaryDirectory() as directory:
            target, link = Path(directory) / "target", Path(directory) / "link"
            target.write_text("preserve")
            link.symlink_to(target)
            with self.assertRaises(ValueError):
                main(["--input", str(EXAMPLE), "--output", str(link)])
            self.assertEqual(target.read_text(), "preserve")
