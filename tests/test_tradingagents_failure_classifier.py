"""Offline classification of TradingAgents errors and warnings."""
import unittest

from scripts.tradingagents_failure_classifier import classify_log


class FailureClassifierTests(unittest.TestCase):
    def test_model_error_takes_priority_over_optional_source_warnings(self):
        log = ("FRED_API_KEY environment variable is not set\n"
               "Yahoo Finance has no news articles tagged 002517.SZ\n"
               "ValueError: Unexpected response type from OpenAI-compatible endpoint. "
               "Expected a dict or openai.BaseModel, got NoneType: None")
        self.assertEqual(classify_log(log)[0], "model_response_invalid")

    def test_optional_warning_not_misreported_as_model_failure(self):
        self.assertEqual(classify_log("FRED_API_KEY environment variable is not set")[0],
                         "optional_macro_unavailable")

    def test_date_and_missing_key(self):
        self.assertEqual(classify_log("分析日期必须使用 YYYY-MM-DD")[0],
                         "invalid_analysis_date")
        self.assertEqual(classify_log(
            "请先在仓库 Actions secrets 中配置 DEEPSEEK_API_KEY")[0], "missing_api_key")

    def test_unknown(self):
        self.assertEqual(classify_log("something else")[0], "unknown")


if __name__ == "__main__":
    unittest.main()
