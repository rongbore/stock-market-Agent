"""Exercise the real analysis entrypoint without any network or paid LLM calls."""
import json
import os
import sys
import tempfile
import types
import unittest
from pathlib import Path
from unittest.mock import patch

from scripts import analyze
from scripts.artifact_secret_guard import validate_artifact_secrets
from scripts.report_contract import validate_reports_root


class MockedAnalyzeEntrypointTests(unittest.TestCase):
    def test_entrypoint_writes_upload_ready_artifacts(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            summary = root / "summary.md"
            observed = {}

            class FakeGraph:
                def __init__(self, *, selected_analysts, config):
                    observed["analysts"] = selected_analysts
                    observed["config"] = config

                def propagate(self, ticker, trade_date):
                    observed["ticker"] = ticker
                    observed["date"] = trade_date
                    return {"synthetic": True}, None

                def save_reports(self, state, ticker, html=True):
                    self_test = Path("results/reports") / ticker / observed["date"]
                    self_test.mkdir(parents=True, exist_ok=True)
                    output = self_test / "complete_report.html"
                    output.write_text("<html><body>OFFLINE SYNTHETIC TEST ONLY</body></html>",
                                      encoding="utf-8")
                    return str(output)

            package = types.ModuleType("tradingagents")
            package.__path__ = []
            config_mod = types.ModuleType("tradingagents.default_config")
            config_mod.DEFAULT_CONFIG = {}
            graph_pkg = types.ModuleType("tradingagents.graph")
            graph_pkg.__path__ = []
            graph_mod = types.ModuleType("tradingagents.graph.trading_graph")
            graph_mod.TradingAgentsGraph = FakeGraph
            modules = {
                "tradingagents": package,
                "tradingagents.default_config": config_mod,
                "tradingagents.graph": graph_pkg,
                "tradingagents.graph.trading_graph": graph_mod,
            }
            env = {
                "ANALYSIS_TICKER": "000776.SZ",
                "ANALYSIS_DATE": "2026-01-01",
                "ANALYSIS_MODEL": "offline-test",
                "DEEPSEEK_API_KEY": "synthetic-not-a-real-secret",
                "GITHUB_RUN_ID": "1234",
                "GITHUB_STEP_SUMMARY": str(summary),
            }
            previous = Path.cwd()
            try:
                os.chdir(root)
                with patch.dict(sys.modules, modules), patch.dict(os.environ, env):
                    analyze.main()
            finally:
                os.chdir(previous)

            reports = root / "results/reports"
            self.assertEqual(validate_reports_root(reports, require_metadata=True), [])
            self.assertEqual(validate_artifact_secrets(
                reports, secrets=["synthetic-not-a-real-secret"]), [])
            report_dir = reports / "000776.SZ" / "2026-01-01"
            manifest = json.loads((report_dir / "run_provenance.json").read_text())
            evidence = json.loads((report_dir / "evidence_bundle.json").read_text())
            self.assertEqual(manifest["ticker"], "000776.SZ")
            self.assertEqual(manifest["github_run_id"], "1234")
            self.assertEqual(evidence["records"], [])
            self.assertFalse(evidence["source_content_verified"])
            self.assertEqual(observed["analysts"], ["market", "news", "fundamentals"])
            self.assertEqual(observed["config"]["llm_provider"], "deepseek")
            self.assertIn("000776.SZ", summary.read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
