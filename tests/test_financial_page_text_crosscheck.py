import unittest
from scripts.financial_page_text_crosscheck import (
    check_disclosure_page_evidence,
    check_page_text,
)


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

    def disclosure_evidence(self, **changes):
        page = {
            "symbol": "000776.SZ", "announcement_date": "2026-10-20",
            "source_url": "https://static.cninfo.com.cn/finalpage/2026/report.pdf",
            "retrieved_at": "2026-11-01T02:00:00+00:00",
            "file_sha256": "a" * 64, "page": 4,
            "text": "营业收入 123.45 亿元",
            "text_extraction_status": "text_extracted_unverified",
            "official_origin_verified": False, "source_content_verified": False,
            "financial_meaning_verified": False,
            "historical_point_in_time_verified": False,
        }
        page.update(changes)
        return {"schema_version": "0.1", "page_count": 1,
                "all_pages_verified": False, "pages": [page]}

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
                              "text": "营业收入\n123.45"}])[0]
        self.assertFalse(result["metric_label_near_value_unverified"])

    def test_wrong_label_is_not_proximity_evidence(self):
        result = self.check([{"file_sha256": "a" * 64, "page": 4,
                              "text": "总资产 123.45"}])[0]
        self.assertFalse(result["metric_label_near_value_unverified"])

    def test_unit_label_immediately_after_value(self):
        result = self.check([{"file_sha256": "a" * 64, "page": 4,
                              "text": "营业收入 123.45 亿元"}])[0]
        self.assertTrue(result["unit_label_near_value_unverified"])
        self.assertFalse(result["financial_meaning_verified"])

    def test_wrong_unit_is_not_unit_evidence(self):
        result = self.check([{"file_sha256": "a" * 64, "page": 4,
                              "text": "营业收入 123.45 万元"}])[0]
        self.assertFalse(result["unit_label_near_value_unverified"])

    def test_unit_on_other_line_is_not_evidence(self):
        result = self.check([{"file_sha256": "a" * 64, "page": 4,
                              "text": "营业收入 123.45\n亿元"}])[0]
        self.assertFalse(result["unit_label_near_value_unverified"])

    def test_unit_far_from_value_is_not_evidence(self):
        result = self.check([{"file_sha256": "a" * 64, "page": 4,
                              "text": "亿元" + "其他内容" * 8 + "123.45"}])[0]
        self.assertFalse(result["unit_label_near_value_unverified"])

    def test_period_date_before_value_same_line(self):
        result = self.check([{"file_sha256": "a" * 64, "page": 4,
                              "text": "2026年9月30日 营业收入 123.45 亿元"}])[0]
        self.assertTrue(result["period_end_near_value_unverified"])
        self.assertFalse(result["financial_meaning_verified"])

    def test_wrong_period_is_not_period_evidence(self):
        result = self.check([{"file_sha256": "a" * 64, "page": 4,
                              "text": "2025-09-30 营业收入 123.45 亿元"}])[0]
        self.assertFalse(result["period_end_near_value_unverified"])

    def test_period_after_value_is_not_period_evidence(self):
        result = self.check([{"file_sha256": "a" * 64, "page": 4,
                              "text": "营业收入 123.45 亿元 2026-09-30"}])[0]
        self.assertFalse(result["period_end_near_value_unverified"])

    def test_period_on_other_line_is_not_period_evidence(self):
        result = self.check([{"file_sha256": "a" * 64, "page": 4,
                              "text": "2026-09-30\n营业收入 123.45"}])[0]
        self.assertFalse(result["period_end_near_value_unverified"])

    def test_multi_column_table_is_flagged_as_ambiguous(self):
        result = self.check([{"file_sha256": "a" * 64, "page": 4,
                              "text": "项目 本期金额 上期金额\n营业收入 123.45 98.76"}])[0]
        self.assertTrue(result["table_column_ambiguous_unverified"])
        self.assertFalse(result["financial_meaning_verified"])

    def test_single_column_not_flagged(self):
        result = self.check([{"file_sha256": "a" * 64, "page": 4,
                              "text": "营业收入 123.45 亿元"}])[0]
        self.assertFalse(result["table_column_ambiguous_unverified"])

    def test_table_headings_without_multiple_row_numbers_not_flagged(self):
        result = self.check([{"file_sha256": "a" * 64, "page": 4,
                              "text": "本期金额 上期金额\n营业收入 123.45"}])[0]
        self.assertFalse(result["table_column_ambiguous_unverified"])

    def test_other_column_heading_pair_flagged(self):
        result = self.check([{"file_sha256": "a" * 64, "page": 4,
                              "text": "期末余额 期初余额\n总资产 123.45 111.00"}])[0]
        self.assertTrue(result["table_column_ambiguous_unverified"])

    def test_positive_value_does_not_match_negative_number(self):
        result = self.check([{"file_sha256": "a" * 64, "page": 4,
                              "text": "营业收入 -123.45 亿元"}])[0]
        self.assertEqual(result["status"], "literal_value_not_found")
        self.assertFalse(result["metric_label_near_value_unverified"])
        self.assertFalse(result["unit_label_near_value_unverified"])

    def test_positive_value_does_not_match_explicit_plus_or_unicode_minus(self):
        for text in ("营业收入 +123.45", "营业收入 −123.45"):
            with self.subTest(text=text):
                result = self.check([{"file_sha256": "a" * 64, "page": 4,
                                      "text": text}])[0]
                self.assertEqual(result["status"], "literal_value_not_found")

    def test_value_does_not_match_thousands_group_fragment(self):
        result = self.check([{"file_sha256": "a" * 64, "page": 4,
                              "text": "营业收入 1,123.45 亿元"}])[0]
        self.assertEqual(result["status"], "literal_value_not_found")

    def test_negative_claim_matches_exact_negative_number(self):
        self.claim["value"] = "-123.45"
        result = self.check([{"file_sha256": "a" * 64, "page": 4,
                              "text": "营业收入 -123.45 亿元"}])[0]
        self.assertEqual(result["status"], "literal_value_found_unverified")
        self.assertTrue(result["metric_label_near_value_unverified"])

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

    def test_downloaded_page_evidence_carries_source_and_retrieval_citation(self):
        result = check_disclosure_page_evidence(
            [self.claim], self.fp, self.disclosure_evidence(),
            "000776.SZ", "2026-10-30")[0]
        self.assertEqual(result["status"], "literal_value_found_unverified")
        self.assertEqual(result["source_url"],
                         "https://static.cninfo.com.cn/finalpage/2026/report.pdf")
        self.assertEqual(result["retrieved_at"], "2026-11-01T02:00:00+00:00")
        self.assertTrue(result["retrieval_date_after_research_date"])
        self.assertFalse(result["source_url_match_verified"])
        self.assertFalse(result["historical_point_in_time_verified"])

    def test_downloaded_page_date_must_match_claim_date(self):
        evidence = self.disclosure_evidence(announcement_date="2026-10-21")
        with self.assertRaisesRegex(ValueError, "announcement date differs"):
            check_disclosure_page_evidence(
                [self.claim], self.fp, evidence, "000776.SZ", "2026-10-30")

    def test_downloaded_page_must_remain_unverified(self):
        evidence = self.disclosure_evidence(source_content_verified=True)
        with self.assertRaisesRegex(ValueError, "remain unverified"):
            check_disclosure_page_evidence(
                [self.claim], self.fp, evidence, "000776.SZ", "2026-10-30")

    def test_downloaded_page_rejects_unapproved_url_or_timezone_missing(self):
        for changes in (
            {"source_url": "https://static.cninfo.com.cn.evil.test/finalpage/a.pdf"},
            {"retrieved_at": "2026-11-01T02:00:00"},
        ):
            with self.subTest(changes=changes), self.assertRaises(ValueError):
                check_disclosure_page_evidence(
                    [self.claim], self.fp, self.disclosure_evidence(**changes),
                    "000776.SZ", "2026-10-30")

    def test_duplicate_downloaded_page_citation_rejected(self):
        evidence = self.disclosure_evidence()
        evidence["pages"] = evidence["pages"] * 2
        evidence["page_count"] = 2
        with self.assertRaisesRegex(ValueError, "duplicate"):
            check_disclosure_page_evidence(
                [self.claim], self.fp, evidence, "000776.SZ", "2026-10-30")


if __name__ == "__main__":
    unittest.main()
