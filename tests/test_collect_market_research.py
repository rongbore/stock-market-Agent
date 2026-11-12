import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from scripts.collect_market_research import collect_market_research, main

ROOT = Path(__file__).resolve().parents[1]


def snapshot():
    return json.loads((ROOT/"examples/backtest/SYNTHETIC_sma_oos_config.json").read_text())["snapshot"]


class CollectionEntryTests(unittest.TestCase):
    def run_collection(self, fetcher):
        s = snapshot()
        return collect_market_research(s["symbol"], s["start_date"], s["end_date"], "eastmoney", fetcher=fetcher)

    def test_injected_collection_runs_all_offline_stages_without_claiming_live_acceptance(self):
        result = self.run_collection(lambda *args, **kwargs: snapshot())
        self.assertEqual(result["status"], "COLLECTED_RESEARCH_UNVERIFIED")
        self.assertEqual(result["research"]["bundle"]["succeeded_count"], 1)
        self.assertIn("单源收盘价", result["research"]["summary_markdown"])
        self.assertIn("批量研究任务", result["dashboard_html"])
        self.assertFalse(result["source_verified"])

    def test_collection_failure_is_sanitized_and_has_no_success_payload(self):
        def fail(*args, **kwargs):
            raise RuntimeError("SECRET_DO_NOT_LOG")
        result = self.run_collection(fail)
        self.assertEqual(result["stage"], "collection")
        self.assertNotIn("SECRET_DO_NOT_LOG", json.dumps(result))
        self.assertNotIn("snapshot", result)

    def test_empty_wrong_source_and_invalid_units_fail_validation(self):
        for field, value in (("records", []), ("upstream", "sina"), ("volume_unit", "unknown")):
            s = snapshot()
            s[field] = value
            with self.subTest(field=field):
                result = self.run_collection(lambda *args, **kwargs: s)
                self.assertEqual(result["stage"], "validation")
                self.assertEqual(result["status"], "FAILED")
                self.assertNotIn("research", result)

    def test_invalid_request_never_calls_provider(self):
        def unexpected(*args, **kwargs):
            self.fail("provider must not run")
        with self.assertRaises(ValueError):
            collect_market_research("../x", "2026-01-01", "2026-11-01", "eastmoney", fetcher=unexpected)
        with self.assertRaises(ValueError):
            collect_market_research("000776.SZ", "2024-01-01", "2026-11-01", "eastmoney", fetcher=unexpected)

    def test_cli_requires_explicit_network_opt_in(self):
        with self.assertRaises(SystemExit) as result:
            main(["--symbol", "000776.SZ", "--start-date", "2026-11-02", "--end-date", "2026-11-06",
                  "--upstream", "eastmoney", "--output", "unused.json"])
        self.assertEqual(result.exception.code, 2)

    def test_failed_cli_writes_diagnostic_with_nonzero_exit_and_never_overwrites(self):
        with tempfile.TemporaryDirectory() as folder:
            output = Path(folder)/"result.json"
            args = ["--symbol", "000776.SZ", "--start-date", "2026-11-02", "--end-date", "2026-11-06",
                    "--upstream", "eastmoney", "--allow-network", "--output", str(output)]
            with patch("scripts.collect_market_research.fetch_a_share_daily", side_effect=RuntimeError("private")):
                self.assertEqual(main(args), 2)
            original = output.read_bytes()
            self.assertEqual(json.loads(original)["status"], "FAILED")
            with self.assertRaises(FileExistsError):
                main(args)
            self.assertEqual(output.read_bytes(), original)

    def test_output_preflight_failure_never_calls_network_provider(self):
        with tempfile.TemporaryDirectory() as folder:
            output = Path(folder)/"result.json"
            args = ["--symbol", "000776.SZ", "--start-date", "2026-11-02",
                    "--end-date", "2026-11-06", "--upstream", "eastmoney",
                    "--allow-network", "--output", str(output)]
            with patch("scripts.collect_market_research.tempfile.NamedTemporaryFile",
                       side_effect=PermissionError("destination unavailable")):
                with patch("scripts.collect_market_research.fetch_a_share_daily") as provider:
                    with self.assertRaises(PermissionError):
                        main(args)
                    provider.assert_not_called()
            self.assertFalse(output.exists())

    def test_exclusive_link_failure_cleans_temporary_file(self):
        with tempfile.TemporaryDirectory() as folder:
            output = Path(folder)/"result.json"
            args = ["--symbol", "000776.SZ", "--start-date", "2026-11-02",
                    "--end-date", "2026-11-06", "--upstream", "eastmoney",
                    "--allow-network", "--output", str(output)]
            with patch("scripts.collect_market_research.fetch_a_share_daily",
                       side_effect=RuntimeError("offline")):
                with patch("scripts.collect_market_research.os.link",
                           side_effect=OSError("hard links unsupported")):
                    with self.assertRaises(OSError):
                        main(args)
            self.assertEqual(list(Path(folder).iterdir()), [])
