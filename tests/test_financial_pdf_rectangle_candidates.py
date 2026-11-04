import unittest

from scripts.financial_pdf_rectangle_candidates import rectangle_region_candidates


def rect(x0, top, x1, bottom, page=1):
    return {"page": page, "x0": x0, "top": top, "x1": x1, "bottom": bottom}


class RectangleRegionCandidateTests(unittest.TestCase):
    def test_large_rectangle_is_candidate_not_verified(self):
        result = rectangle_region_candidates([rect(10, 20, 300, 200)])
        self.assertEqual(result["regions"][0]["bbox"], [10, 20, 300, 200])
        self.assertFalse(result["table_boundaries_verified"])

    def test_small_rectangle_is_ignored(self):
        self.assertEqual(rectangle_region_candidates([rect(10, 10, 20, 20)])["regions"], [])

    def test_overlapping_rectangles_are_withheld(self):
        result = rectangle_region_candidates([
            rect(0, 0, 300, 200), rect(100, 100, 350, 250)])
        self.assertEqual(result["regions"], [])
        self.assertEqual(result["ambiguous_overlap_count"], 2)

    def test_separate_pages_can_have_same_coordinates(self):
        result = rectangle_region_candidates([
            rect(0, 0, 300, 200), rect(0, 0, 300, 200, page=2)])
        self.assertEqual(len(result["regions"]), 2)

    def test_rejects_invalid_coordinates(self):
        for bad in (rect(0, 0, float("nan"), 100), rect(10, 0, 5, 100)):
            with self.subTest(bad=bad), self.assertRaises(ValueError):
                rectangle_region_candidates([bad])

    def test_rejects_invalid_limits(self):
        with self.assertRaises(ValueError):
            rectangle_region_candidates([], min_width=float("inf"))

    def test_rejects_too_many_rectangles(self):
        with self.assertRaises(ValueError):
            rectangle_region_candidates([rect(0, 0, 100, 100)] * 2001)


if __name__ == "__main__":
    unittest.main()
