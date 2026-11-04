import unittest
from scripts.financial_page_text_crosscheck import check_page_text


class FinancialPageTextCrosscheckTests(unittest.TestCase):
    def setUp(self):
        self.fp = [{"symbol": "000776.SZ", "file_sha256": "a" * 64,
                    "announcement_date": "2026-10-20",
                    "official_origin_verified": False, "source_content_verified": False}]
        self.claim = {"symbol": "000776.SZ", "metric": "revenue", "value": "123.45",
                      "unit": "CNY_100000000", "period_end": "2026-09-30",
                      "announcement_date": "2026-10-20", "file_sha256": "a" * 64,
                      "page": 4}

    def check(self, pages):
        return check_page_text([self.claim], self.fp, pages, "000776.SZ", "2026-10-30")

    def test_literal_match_does_not_verify_meaning(self):
        result = self.check([{"file_sha256": "a" * 64, "page": 4,
                              "text": "示例数字 123.45；不代表营业收入"}])[0]
        self.assertEqual(result["status"], "literal_value_found_unverified")
        self.assertFalse(result["financial_meaning_verified"])

    def test_no_partial_number_match(self):
        result = self.check([{"file_sha256": "a" * 64, "page": 4,
                              "text": "123.456 or 9123.45"}])[0]
        self.assertEqual(result["status"], "literal_value_not_found")

    def test_metric_label_before_value_on_same_line(self):
        result = self.check([{"file_sha256": "a" * 64, "page": 4,
                              "text": "营业收入 123.45"}])[0]
        self.assertTrue(result["metric_label_near_value_unverified"])
        self.assertFalse(result["financial_meaning_verified"])

    def test_label_after_value_is_not_proximity_evidence(self):
        result = self.check([{"file_sha256": "a" * 64, "page": 4,
                              "text": "123.45 营业收入"}])[0]
        self.assertFalse(result["metric_label_near_value_unverified"])

    def test_label_on_other_line_is_not_proximity_evidence(self):
        result = self.check([{"file_sha256": "a" * 64, "page": 4,
                              "text": "营业收入\\n123.45"}])[0]
        self.assertFalse(result["metric_label_near_value_unverified"])

    def test_wrong_label_is_not_proximity_evidence(self):
        result = self.check([{"file_sha256": "a" * 64, "page": 4,
                              "text": "总资产 123.45"}])[0]
        self.assertFalse(result["metric_label_near_value_unverified"])

    def test_missing_page_is_explicit(self):
        self.assertEqual(self.check([])[0]["status"], "page_text_missing")

    def test_duplicate_pages_rejected(self):
        page = {"file_sha256": "a" * 64, "page": 4, "text": "123.45"}
        with self.assertRaisesRegex(ValueError, "duplicate"):
            self.check([page, page])

    def test_unrelated_pdf_hash_does_not_match(self):
        result = self.check([{"file_sha256": "b" * 64, "page": 4,
                              "text": "123.45"}])[0]
        self.assertEqual(result["status"], "page_text_missing")


if __name__ == "__main__":
    unittest.main()
