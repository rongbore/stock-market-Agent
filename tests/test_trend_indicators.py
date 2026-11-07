import unittest
from scripts.trend_indicators import moving_average, technical_summary


class TrendIndicatorTests(unittest.TestCase):
    def test_no_padding_before_full_window(self):
        self.assertEqual(moving_average([1, 2, 3, 4, 5, 6], 5),
                         [None, None, None, None, 3.0, 4.0])

    def test_short_series_no_ma20_claim(self):
        result = technical_summary({"dates": ["2026-01-01"] * 5,
                                    "prices": [10, 11, 12, 13, 14]})
        self.assertEqual(result["status"], "insufficient_data")
        self.assertIsNone(result["ma20"][-1])
        self.assertFalse(result["investment_signal"])

    def test_20_points_allow_descriptive_comparison(self):
        result = technical_summary({"dates": [str(i) for i in range(20)],
                                    "prices": list(range(1, 21))})
        self.assertEqual(result["status"], "descriptive_only")
        self.assertIn("MA5高于MA20", result["observation"])

    def test_invalid_numeric_and_misalignment_rejected(self):
        with self.assertRaisesRegex(ValueError, "invalid close"):
            moving_average([10, float("nan")], 2)
        with self.assertRaisesRegex(ValueError, "align"):
            technical_summary({"dates": ["2026-01-01"], "prices": [1, 2]})

    def test_empty_series_is_insufficient(self):
        self.assertEqual(technical_summary({"dates": [], "prices": []})["status"],
                         "insufficient_data")


if __name__ == "__main__":
    unittest.main()
