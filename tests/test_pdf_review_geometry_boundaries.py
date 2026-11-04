import unittest

from scripts.pdf_manual_review_validation import validate_review_annotations
from scripts.pdf_sample_acceptance_gate import assess_sample

SHA = "a" * 64


class PdfReviewGeometryBoundaryTests(unittest.TestCase):
    def test_empty_candidate_review_not_complete(self):
        report = validate_review_annotations(
            {"file_sha256": SHA, "candidates": []},
            {"file_sha256": SHA, "decisions": []},
        )
        self.assertFalse(report["review_complete"])
        bundle = {
            "source_record": {"file_sha256": SHA, "symbol": "000776.SZ",
                              "announcement_date_claimed": "2026-10-20",
                              "source_file_match_verified": False,
                              "official_origin_verified": False,
                              "financial_meaning_verified": False},
            "review_manifest": {"file_sha256": SHA, "candidate_count": 0,
                                "symbol": "000776.SZ", "announcement_date_claimed": "2026-10-20",
                                "official_origin_verified": False, "financial_meaning_verified": False,
                                "candidates": []},
            "sample_checked_with_real_pdf_parser": True,
            "official_origin_verified": False, "financial_meaning_verified": False,
        }
        result = assess_sample(bundle, report)
        self.assertFalse(result["review_complete"])
        self.assertFalse(result["offline_review_ready"])
        self.assertIn("no_rectangle_candidates", result["blockers"])
        self.assertIn("manual_review_incomplete", result["blockers"])

    def test_rejects_inverted_and_zero_area_boxes(self):
        for bbox in ([20, 10, 10, 20], [10, 20, 20, 10], [10, 10, 10, 20],
                     [10, 10, 20, 10]):
            with self.subTest(bbox=bbox):
                with self.assertRaisesRegex(ValueError, "geometry"):
                    validate_review_annotations(
                        {"file_sha256": SHA, "candidates": [{"page": 1, "bbox": bbox}]},
                        {"file_sha256": SHA, "decisions": []},
                    )


if __name__ == "__main__":
    unittest.main()
