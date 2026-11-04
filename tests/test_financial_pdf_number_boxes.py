import unittest

from scripts.financial_pdf_number_boxes import number_boxes


def chars(text, page=1, x=10, y=20, step=5):
    return [
        {"page": page, "text": c, "bbox": [x + i * step, y, x + i * step + 4, y + 9]}
        for i, c in enumerate(text)
    ]


class PdfNumberBoxesTests(unittest.TestCase):
    def test_decimal_bbox(self):
        result = number_boxes(chars("123.45"))
        self.assertEqual(result["numbers"][0]["text"], "123.45")
        self.assertEqual(result["numbers"][0]["bbox"], [10, 20, 39, 29])
        self.assertFalse(result["column_ownership_verified"])

    def test_negative_number(self):
        self.assertEqual(number_boxes(chars("-123.45"))["numbers"][0]["text"], "-123.45")

    def test_rejects_thousands_separator_without_partial_claim(self):
        self.assertEqual(number_boxes(chars("1,123.45"))["number_count"], 0)

    def test_does_not_join_across_letters(self):
        result = number_boxes(chars("12a34"))
        self.assertEqual([v["text"] for v in result["numbers"]], ["12", "34"])

    def test_does_not_join_across_rows_or_large_gaps(self):
        spans = chars("12") + chars("34", y=50) + chars("56", x=100)
        result = number_boxes(spans)
        self.assertEqual([v["text"] for v in result["numbers"]], ["12", "56", "34"])

    def test_rejects_invalid_geometry(self):
        with self.assertRaises(ValueError):
            number_boxes([{"page": 1, "text": "1", "bbox": [0, 0, float("nan"), 9]}])
        with self.assertRaises(ValueError):
            number_boxes(chars("12"), max_gap=-1)

    def test_unverified_flags(self):
        result = number_boxes(chars("42"))
        self.assertFalse(result["financial_meaning_verified"])
        self.assertFalse(result["numbers"][0]["column_ownership_verified"])


if __name__ == "__main__":
    unittest.main()
