"""Validate analysis inputs without invoking paid model APIs."""
import os
import unittest
from unittest.mock import patch

from scripts.analyze import read_inputs


class InputTests(unittest.TestCase):
    def test_default_ticker(self):
        with patch.dict(os.environ, {"ANALYSIS_TICKER": "", "ANALYSIS_DATE": ""}):
            with self.assertRaises(ValueError):
                read_inputs()

    def test_supported_ticker_format(self):
        with patch.dict(os.environ, {"ANALYSIS_TICKER": "600519.ss", "ANALYSIS_DATE": ""}):
            ticker, _, _ = read_inputs()
            self.assertEqual(ticker, "600519.SS")

    def test_invalid_ticker_rejected(self):
        with patch.dict(os.environ, {"ANALYSIS_TICKER": "NVDA;echo bad", "ANALYSIS_DATE": ""}):
            with self.assertRaises(ValueError):
                read_inputs()

    def test_invalid_date_rejected(self):
        with patch.dict(os.environ, {"ANALYSIS_TICKER": "NVDA", "ANALYSIS_DATE": "2026-99-99"}):
            with self.assertRaises(ValueError):
                read_inputs()

    def test_blank_model_rejected(self):
        with patch.dict(os.environ, {"ANALYSIS_TICKER": "NVDA", "ANALYSIS_DATE": "", "ANALYSIS_MODEL": "  "}):
            with self.assertRaises(ValueError):
                read_inputs()


if __name__ == "__main__":
    unittest.main()
