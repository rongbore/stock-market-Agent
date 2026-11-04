import unittest

from scripts.financial_pdf_column_hints import column_proximity_hints


def span(text, x, page=1, y=10):
    return {"page": page, "text": text, "bbox": [x, y, x + 40, y + 10]}


class PdfColumnHintsTests(unittest.TestCase):
    def setUp(self):
        self.headers = [span("本期金额", 100), span("上期金额", 300)]

    def test_nearest_header_is_unverified_hint(self):
        result = column_proximity_hints([span("123.45", 110, y=50)], self.headers)
        candidate = result["candidates"][0]
        self.assertEqual(candidate["nearest_header_hint_unverified"], "本期金额")
        self.assertFalse(candidate["column_ownership_verified"])
        self.assertFalse(result["financial_meaning_verified"])

    def test_previous_period_hint(self):
        result = column_proximity_hints([span("98.76", 305, y=50)], self.headers)
        self.assertEqual(result["candidates"][0]["nearest_header_hint_unverified"], "上期金额")

    def test_missing_header_pair_is_ambiguous(self):
        result = column_proximity_hints([span("1", 100)], self.headers[:1])
        self.assertIsNone(result["candidates"][0]["nearest_header_hint_unverified"])

    def test_repeated_header_pairs_are_ambiguous(self):
        headers = self.headers + [span("本期金额", 100, y=200), span("上期金额", 300, y=200)]
        result = column_proximity_hints([span("1", 100)], headers)
        self.assertEqual(result["candidates"][0]["reason"], "missing_or_ambiguous_header_pair")

    def test_wrong_page_is_not_assigned(self):
        result = column_proximity_hints([span("1", 100, page=2)], self.headers)
        self.assertIsNone(result["candidates"][0]["nearest_header_hint_unverified"])

    def test_far_and_equidistant_numbers_are_ambiguous(self):
        far = column_proximity_hints([span("1", 700)], self.headers)
        self.assertEqual(far["candidates"][0]["reason"], "number_far_from_headers")
        middle = column_proximity_hints([span("1", 200)], self.headers)
        self.assertEqual(middle["candidates"][0]["reason"], "equidistant_from_headers")

    def test_rejects_invalid_inputs(self):
        with self.assertRaises(ValueError):
            column_proximity_hints([span("1", 100)], self.headers, max_dx=float("nan"))
        with self.assertRaisesRegex(ValueError, "unsupported"):
            column_proximity_hints([span("1", 100)], [span("未知表头", 100)])


if __name__ == "__main__":
    unittest.main()
