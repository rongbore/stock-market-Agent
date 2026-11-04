import unittest

from scripts.pdf_manual_review_validation import validate_review_annotations


SHA = "a" * 64


def manifest():
    return {"file_sha256": SHA, "candidates": [
        {"page": 1, "bbox": [10, 20, 300, 200]},
        {"page": 2, "bbox": [10, 20, 300, 200]},
    ]}


def annotations(decisions):
    return {"file_sha256": SHA, "decisions": decisions}


def decision(index, status="accepted_by_reviewer", page=None, reviewer="Analyst"):
    return {"candidate_index": index, "review_status": status,
            "page": index + 1 if page is None else page,
            "bbox": [10, 20, 300, 200], "reviewer": reviewer}


class ManualReviewValidationTests(unittest.TestCase):
    def test_completed_review_is_not_financial_verification(self):
        result = validate_review_annotations(
            manifest(), annotations([decision(0), decision(1, "rejected_by_reviewer")]))
        self.assertTrue(result["review_complete"])
        self.assertFalse(result["financial_meaning_verified"])
        self.assertFalse(result["official_origin_verified"])

    def test_partial_review_stays_pending(self):
        result = validate_review_annotations(manifest(), annotations([decision(0)]))
        self.assertFalse(result["review_complete"])

    def test_rejects_stale_file_hash(self):
        with self.assertRaisesRegex(ValueError, "fingerprint"):
            validate_review_annotations(manifest(), {"file_sha256": "b" * 64, "decisions": []})

    def test_rejects_wrong_page(self):
        with self.assertRaisesRegex(ValueError, "coordinates"):
            validate_review_annotations(manifest(), annotations([decision(0, page=2)]))

    def test_rejects_duplicate_decisions(self):
        with self.assertRaisesRegex(ValueError, "duplicate"):
            validate_review_annotations(manifest(), annotations([decision(0), decision(0)]))

    def test_rejects_missing_reviewer(self):
        with self.assertRaisesRegex(ValueError, "reviewer"):
            validate_review_annotations(manifest(), annotations([decision(0, reviewer="")]))

    def test_rejects_unknown_status(self):
        with self.assertRaisesRegex(ValueError, "status"):
            validate_review_annotations(manifest(), annotations([decision(0, "verified_financial_table")]))

    def test_rejects_nonfinite_bbox(self):
        m = manifest()
        m["candidates"][0]["bbox"][0] = float("nan")
        with self.assertRaisesRegex(ValueError, "bbox"):
            validate_review_annotations(m, annotations([]))


if __name__ == "__main__":
    unittest.main()
