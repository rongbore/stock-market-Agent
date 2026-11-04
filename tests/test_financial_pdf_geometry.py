import unittest

from scripts.financial_pdf_geometry import column_candidates, inspect_spans


class FinancialPdfGeometryTests(unittest.TestCase):
    def setUp(self):
        self.spans = [
            {"page": 4, "text": "营业收入", "bbox": [10, 50, 80, 62]},
            {"page": 4, "text": "123.45", "bbox": [140, 50, 185, 62]},
            {"page": 4, "text": "98.76", "bbox": [250, 50, 290, 62]},
        ]

    def test_candidates_preserve_positions_without_claiming_column(self):
        result = column_candidates(self.spans, 4, "123.45")
        self.assertEqual(result["candidate_count"], 1)
        self.assertEqual(result["candidates"][0]["bbox"], [140, 50, 185, 62])
        self.assertFalse(result["column_ownership_verified"])
        self.assertFalse(result["candidates"][0]["column_ownership_verified"])

    def test_geometry_diagnostics_are_unverified(self):
        result = inspect_spans(self.spans)
        self.assertEqual(result["pages"], [4])
        self.assertFalse(result["official_origin_verified"])
        self.assertFalse(result["financial_meaning_verified"])

    def test_reject_nonfinite_and_inverted_boxes(self):
        for bbox in ([0, 0, float("nan"), 1], [10, 0, 5, 1], [True, 0, 5, 1]):
            with self.subTest(bbox=bbox), self.assertRaises(ValueError):
                inspect_spans([{"page": 1, "text": "123", "bbox": bbox}])

    def test_reject_excessive_and_invalid_spans(self):
        with self.assertRaises(ValueError):
            inspect_spans(self.spans * 700)
        with self.assertRaises(ValueError):
            inspect_spans([{"page": True, "text": "123", "bbox": [0, 0, 1, 1]}])

    def test_signed_number_does_not_match_positive_candidate(self):
        spans = [{"page": 1, "text": "-123.45", "bbox": [0, 0, 40, 10]}]
        self.assertEqual(column_candidates(spans, 1, "123.45")["candidate_count"], 0)
        self.assertEqual(column_candidates(spans, 1, "-123.45")["candidate_count"], 1)


if __name__ == "__main__":
    unittest.main()
