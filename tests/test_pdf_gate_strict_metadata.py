"""Reject truthy or boolean impostors in PDF evidence metadata."""
import unittest

from scripts.pdf_sample_acceptance_gate import assess_sample

SHA = "a" * 64


def evidence():
    candidate = {"page": 1, "bbox": [1, 2, 3, 4]}
    return (
        {
            "source_record": {"file_sha256": SHA, "symbol": "000776.SZ",
                              "announcement_date_claimed": "2026-10-20",
                              "source_file_match_verified": False,
                              "official_origin_verified": False,
                              "financial_meaning_verified": False},
            "review_manifest": {
                "file_sha256": SHA, "candidate_count": 1,
                "symbol": "000776.SZ", "announcement_date_claimed": "2026-10-20",
                "official_origin_verified": False, "financial_meaning_verified": False,
                "candidates": [candidate],
            },
            "sample_checked_with_real_pdf_parser": True,
            "official_origin_verified": False,
            "financial_meaning_verified": False,
        },
        {
            "file_sha256": SHA,
            "review_decisions": [{
                "candidate_index": 0, "page": 1,
                "bbox": [1, 2, 3, 4],
                "review_status": "accepted_by_reviewer",
            }],
            "review_complete": True,
            "official_origin_verified": False,
            "financial_meaning_verified": False,
        },
    )


class PdfGateStrictMetadataTests(unittest.TestCase):
    def test_valid_parser_confirmation(self):
        bundle, review = evidence()
        self.assertTrue(assess_sample(bundle, review)["offline_review_ready"])

    def test_candidate_count_rejects_bool(self):
        bundle, review = evidence()
        bundle["review_manifest"]["candidate_count"] = True
        with self.assertRaisesRegex(ValueError, "candidate count"):
            assess_sample(bundle, review)

    def test_parser_confirmation_requires_literal_true(self):
        for value in (1, "true", "yes", [], None, False):
            with self.subTest(value=value):
                bundle, review = evidence()
                bundle["sample_checked_with_real_pdf_parser"] = value
                result = assess_sample(bundle, review)
                self.assertFalse(result["offline_review_ready"])
                self.assertIn("real_pdf_parser_not_confirmed", result["blockers"])


if __name__ == "__main__":
    unittest.main()
