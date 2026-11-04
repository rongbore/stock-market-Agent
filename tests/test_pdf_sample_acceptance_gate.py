import unittest

from scripts.pdf_sample_acceptance_gate import assess_sample


SHA = "a" * 64


def evidence():
    candidate = {"page": 1, "bbox": [20, 120, 240, 220]}
    bundle = {
        "source_record": {"file_sha256": SHA},
        "review_manifest": {"file_sha256": SHA, "candidate_count": 1,
                            "candidates": [candidate]},
        "sample_checked_with_real_pdf_parser": True,
        "official_origin_verified": False,
        "financial_meaning_verified": False,
    }
    review = {
        "file_sha256": SHA, "review_complete": True,
        "review_decisions": [{"candidate_index": 0, **candidate,
                              "review_status": "accepted_by_reviewer"}],
        "official_origin_verified": False,
        "financial_meaning_verified": False,
    }
    return bundle, review


class PdfSampleAcceptanceGateTests(unittest.TestCase):
    def test_completed_geometry_review_does_not_pass_release_gate(self):
        result = assess_sample(*evidence())
        self.assertTrue(result["offline_review_ready"])
        self.assertFalse(result["release_evidence_accepted"])
        self.assertIn("official_source_not_verified", result["blockers"])
        self.assertIn("financial_meaning_not_verified", result["blockers"])

    def test_no_candidates_is_blocker(self):
        bundle, review = evidence()
        bundle["review_manifest"]["candidates"] = []
        bundle["review_manifest"]["candidate_count"] = 0
        review["review_decisions"] = []
        result = assess_sample(bundle, review)
        self.assertIn("no_rectangle_candidates", result["blockers"])

    def test_incomplete_review_is_blocker(self):
        bundle, review = evidence()
        review["review_decisions"] = []
        review["review_complete"] = False
        self.assertIn("manual_review_incomplete", assess_sample(bundle, review)["blockers"])

    def test_rejects_mismatched_fingerprint(self):
        bundle, review = evidence()
        review["file_sha256"] = "b" * 64
        with self.assertRaisesRegex(ValueError, "fingerprint"):
            assess_sample(bundle, review)

    def test_rejects_review_coordinate_tampering(self):
        bundle, review = evidence()
        review["review_decisions"][0]["bbox"] = [21, 120, 240, 220]
        with self.assertRaisesRegex(ValueError, "does not match"):
            assess_sample(bundle, review)

    def test_rejects_false_claim_of_completed_review(self):
        bundle, review = evidence()
        review["review_decisions"] = []
        with self.assertRaisesRegex(ValueError, "completion"):
            assess_sample(bundle, review)

    def test_rejects_unexpected_financial_verification_claim(self):
        bundle, review = evidence()
        review["financial_meaning_verified"] = True
        with self.assertRaisesRegex(ValueError, "verified"):
            assess_sample(bundle, review)


if __name__ == "__main__":
    unittest.main()
