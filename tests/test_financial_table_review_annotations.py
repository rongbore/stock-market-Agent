import copy
import unittest

from scripts.financial_table_review_annotations import review_package_sha256, record_table_reviews


class AnnotationTests(unittest.TestCase):
    def setUp(self):
        self.package = {"schema_version": "0.1", "status": "PENDING_MANUAL_VERIFICATION",
                        "file_sha256": "a" * 64, "candidate_count": 2,
                        "financial_meaning_verified": False,
                        "candidates": [{"cell": {"text": "10", "bbox": [0, 0, 10, 10]},
                                        "review_blockers": ["consolidation_scope", "manual_verification"]},
                                       {"cell": {"text": "20"}}]}

    def annotations(self, decisions=None):
        return {"file_sha256": "a" * 64, "package_sha256": review_package_sha256(self.package),
                "decisions": decisions if decisions is not None else [self.decision()]}

    def decision(self, index=0):
        return {"candidate_index": index, "decision": "accepted_by_reviewer",
                "reviewer": "reviewer-supplied-name", "note": "Checked against local page."}

    def test_partial_review_preserves_blockers_and_never_promotes_verification(self):
        original = copy.deepcopy(self.package)
        result = record_table_reviews(self.package, self.annotations())
        self.assertEqual(result["package"], original)
        self.assertEqual(result["pending_count"], 1)
        self.assertEqual(result["decisions"][1]["decision"], "pending_manual_review")
        self.assertFalse(result["all_candidates_decided"])
        self.assertFalse(result["release_evidence_accepted"])
        self.assertFalse(result["reviewer_identity_verified"])
        self.assertEqual(self.package, original)

    def test_changed_number_geometry_or_blockers_invalidates_review(self):
        for field, value in (("text", "11"), ("bbox", [1, 0, 10, 10])):
            annotations = self.annotations()
            package = copy.deepcopy(self.package)
            package["candidates"][0]["cell"][field] = value
            with self.subTest(field=field), self.assertRaisesRegex(ValueError, "fingerprint"):
                record_table_reviews(package, annotations)
        annotations = self.annotations()
        self.package["candidates"][0]["review_blockers"] = []
        with self.assertRaisesRegex(ValueError, "fingerprint"):
            record_table_reviews(self.package, annotations)

    def test_wrong_pdf_and_duplicate_index_rejected(self):
        annotations = self.annotations()
        annotations["file_sha256"] = "b" * 64
        with self.assertRaises(ValueError):
            record_table_reviews(self.package, annotations)
        with self.assertRaises(ValueError):
            record_table_reviews(self.package, self.annotations([self.decision(), self.decision()]))

    def test_complete_review_still_does_not_accept_release_evidence(self):
        result = record_table_reviews(self.package, self.annotations([self.decision(0), self.decision(1)]))
        self.assertTrue(result["all_candidates_decided"])
        self.assertFalse(result["release_evidence_accepted"])
        self.assertFalse(result["financial_meaning_verified"])

    def test_invalid_reviewer_note_or_unknown_flags_rejected(self):
        for key, value in (("reviewer", " "), ("note", ""), ("candidate_index", True)):
            d = self.decision()
            d[key] = value
            with self.subTest(key=key), self.assertRaises(ValueError):
                record_table_reviews(self.package, self.annotations([d]))
        self.package["candidates"][0]["value_verified"] = True
        with self.assertRaisesRegex(ValueError, "verification"):
            review_package_sha256(self.package)

    def test_empty_package_is_not_complete(self):
        self.package["candidates"] = []
        self.package["candidate_count"] = 0
        result = record_table_reviews(self.package, self.annotations([]))
        self.assertFalse(result["all_candidates_decided"])

    def test_canonical_hash_ignores_object_key_order(self):
        reordered = dict(reversed(list(self.package.items())))
        self.assertEqual(review_package_sha256(self.package), review_package_sha256(reordered))
