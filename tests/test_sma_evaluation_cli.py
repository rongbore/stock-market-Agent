from copy import deepcopy
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from scripts.offline_batch_research_runner import _canonical_json_bytes
from scripts.sma_evaluation_cli import build_evaluation_artifact

ROOT = Path(__file__).resolve().parents[1]
EXAMPLE = ROOT / "examples/backtest/SYNTHETIC_sma_oos_config.json"


def config():
    return json.loads(EXAMPLE.read_text())


def cli(source, output):
    return subprocess.run([sys.executable, "-m", "scripts.sma_evaluation_cli", "--input", str(source),
                           "--output", str(output)], cwd=ROOT, capture_output=True, text=True, timeout=20)


class EvaluationCliTests(unittest.TestCase):
    def test_true_cli_synthetic_end_to_end_is_repeatable_and_single_artifact(self):
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "evaluation.json"
            result = cli(EXAMPLE, output)
            self.assertEqual(result.returncode, 0, result.stderr)
            first = output.read_bytes()
            artifact = json.loads(first)
            self.assertEqual(artifact["data_kind_supplied_unverified"], "SYNTHETIC")
            self.assertIn("not actual market data", artifact["data_declaration"])
            self.assertFalse(artifact["verified_performance"])
            evaluation = artifact["evaluation"]
            self.assertEqual(evaluation["test"]["fills"][0]["date"], "2026-11-05")
            self.assertEqual(evaluation["benchmark"]["fills"][0]["date"], "2026-11-05")
            self.assertEqual(evaluation["test"]["assumptions"]["minimum_fee"], 5)
            self.assertIn("max_drawdown_fraction", evaluation["metrics"]["test"])
            again = cli(EXAMPLE, output)
            self.assertEqual(again.returncode, 0, again.stderr)
            self.assertEqual(output.read_bytes(), first)
            self.assertEqual([path.name for path in Path(directory).iterdir()], ["evaluation.json"])

    def test_input_and_payload_hashes_use_documented_canonical_encoding(self):
        source = config()
        original = deepcopy(source)
        artifact = build_evaluation_artifact(source)
        self.assertEqual(source, original)
        self.assertEqual(artifact["config_input_sha256"], hashlib.sha256(_canonical_json_bytes(source)).hexdigest())
        payload = {key: value for key, value in artifact.items() if key != "artifact_payload_sha256"}
        self.assertEqual(artifact["artifact_payload_sha256"], hashlib.sha256(_canonical_json_bytes(payload)).hexdigest())
        changed = deepcopy(source)
        changed["settings"]["commission_bps"] = 10
        self.assertNotEqual(build_evaluation_artifact(changed)["config_input_sha256"], artifact["config_input_sha256"])

    def test_every_fee_setting_is_required_without_default(self):
        for key in ("initial_cash", "board_lot_size", "commission_bps", "minimum_fee", "sell_tax_bps", "slippage_bps"):
            source = config()
            del source["settings"][key]
            with self.subTest(key=key), self.assertRaisesRegex(ValueError, "explicit"):
                build_evaluation_artifact(source)

    def test_rejects_unknown_fields_and_data_declarations(self):
        for level in (None, "settings", "snapshot"):
            source = config()
            target = source if level is None else source[level]
            target["unexpected"] = True
            with self.subTest(level=level), self.assertRaises(ValueError):
                build_evaluation_artifact(source)
        source = config()
        source["data_kind"] = "VERIFIED_MARKET_DATA"
        with self.assertRaises(ValueError):
            build_evaluation_artifact(source)

    def test_unverified_local_declaration_stays_unverified(self):
        source = config()
        source["data_kind"] = "UNVERIFIED_LOCAL"
        result = build_evaluation_artifact(source)
        self.assertIn("origin and historical availability unverified", result["data_declaration"])
        self.assertFalse(result["source_content_verified"])
        self.assertFalse(result["historical_point_in_time_verified"])

    def test_true_cli_bad_config_never_replaces_previous_output(self):
        with tempfile.TemporaryDirectory() as directory:
            source, output = Path(directory) / "config.json", Path(directory) / "result.json"
            output.write_bytes(b"previous valid artifact")
            missing = config()
            del missing["settings"]["minimum_fee"]
            for raw in (b"{broken", b'{"schema_version":"0.1","schema_version":"0.1"}',
                        json.dumps(missing).encode(), EXAMPLE.read_bytes().replace(b'"initial_cash": 10000',
                                                                                  b'"initial_cash": NaN')):
                source.write_bytes(raw)
                completed = cli(source, output)
                self.assertNotEqual(completed.returncode, 0)
                self.assertEqual(output.read_bytes(), b"previous valid artifact")
            self.assertEqual(sorted(p.name for p in Path(directory).iterdir()), ["config.json", "result.json"])

    def test_true_cli_refuses_input_overwrite_and_symlink_output(self):
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / "config.json"
            source.write_bytes(EXAMPLE.read_bytes())
            original = source.read_bytes()
            self.assertNotEqual(cli(source, source).returncode, 0)
            self.assertEqual(source.read_bytes(), original)
            target, link = Path(directory) / "target.json", Path(directory) / "output.json"
            target.write_bytes(b"keep")
            link.symlink_to(target)
            self.assertNotEqual(cli(source, link).returncode, 0)
            self.assertTrue(link.is_symlink())
            self.assertEqual(target.read_bytes(), b"keep")

    def test_true_cli_refuses_hardlinked_config_output(self):
        with tempfile.TemporaryDirectory() as directory:
            source, output = Path(directory) / "config.json", Path(directory) / "result.json"
            source.write_bytes(EXAMPLE.read_bytes())
            os.link(source, output)
            original = source.read_bytes()
            self.assertNotEqual(cli(source, output).returncode, 0)
            self.assertEqual(source.read_bytes(), original)
            self.assertEqual(output.read_bytes(), original)

    def test_finite_bounded_config_is_checked_before_evaluation(self):
        for value in (float("nan"), float("inf"), 10 ** 400):
            source = config()
            source["settings"]["initial_cash"] = value
            with self.subTest(value=str(value)[:30]), self.assertRaises(ValueError):
                build_evaluation_artifact(source)
        source = config()
        source["snapshot"]["records"] *= 101
        with self.assertRaisesRegex(ValueError, "500"):
            build_evaluation_artifact(source)
