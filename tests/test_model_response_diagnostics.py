"""Offline regression for malformed OpenAI-compatible responses."""
import unittest
from unittest.mock import MagicMock, patch

from scripts.analyze import run_graph_with_diagnostics


class ModelResponseDiagnosticsTests(unittest.TestCase):
    def test_none_response_reports_actionable_error_without_retry(self):
        graph = MagicMock()
        graph.propagate.side_effect = ValueError(
            "Unexpected response type from OpenAI-compatible endpoint. "
            "Expected a dict or openai.BaseModel, got NoneType: None"
        )
        with self.assertRaisesRegex(RuntimeError, "模型兼容接口") as ctx:
            run_graph_with_diagnostics(graph, "002517.SZ", "2026-11-05")
        self.assertIsInstance(ctx.exception.__cause__, ValueError)
        graph.propagate.assert_called_once_with("002517.SZ", "2026-11-05")

    def test_unrelated_value_error_preserved(self):
        graph = MagicMock()
        graph.propagate.side_effect = ValueError("unrelated")
        with self.assertRaisesRegex(ValueError, "unrelated"):
            run_graph_with_diagnostics(graph, "002517.SZ", "2026-11-05")
        graph.propagate.assert_called_once()


if __name__ == "__main__":
    unittest.main()
