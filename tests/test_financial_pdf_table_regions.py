import unittest

from scripts.financial_pdf_table_regions import scoped_column_hints


def box(text, x0, y0, x1, y1, page=1):
    return {"page": page, "text": text, "bbox": [x0, y0, x1, y1]}


class PdfTableRegionTests(unittest.TestCase):
    def setUp(self):
        self.regions = [box("", 0, 0, 400, 150), box("", 0, 200, 400, 350)]
        self.headers = [
            box("本期金额", 100, 10, 140, 20),
            box("上期金额", 300, 10, 340, 20),
            box("本期金额", 100, 210, 140, 220),
            box("上期金额", 300, 210, 340, 220),
        ]

    def test_repeated_headers_across_tables_are_scoped(self):
        result = scoped_column_hints(
            [box("123.45", 110, 50, 135, 60)], self.headers, self.regions)
        candidate = result["candidates"][0]
        self.assertEqual(candidate["nearest_header_hint_unverified"], "本期金额")
        self.assertEqual(candidate["region_index_unverified"], 0)
        self.assertFalse(result["table_boundaries_verified"])

    def test_second_table_uses_own_headers(self):
        result = scoped_column_hints(
            [box("98.76", 310, 250, 330, 260)], self.headers, self.regions)
        self.assertEqual(result["candidates"][0]["nearest_header_hint_unverified"], "上期金额")

    def test_outside_region_is_unassigned(self):
        result = scoped_column_hints(
            [box("1", 110, 170, 120, 180)], self.headers, self.regions)
        self.assertIsNone(result["candidates"][0]["nearest_header_hint_unverified"])

    def test_overlapping_regions_are_ambiguous(self):
        regions = self.regions + [box("", 90, 40, 150, 80)]
        result = scoped_column_hints(
            [box("1", 110, 50, 120, 60)], self.headers, regions)
        self.assertEqual(result["candidates"][0]["reason"],
                         "number_outside_or_overlapping_regions")

    def test_no_headers_in_region_does_not_borrow_other_table(self):
        result = scoped_column_hints(
            [box("1", 110, 250, 120, 260)], self.headers[:2], self.regions)
        self.assertIsNone(result["candidates"][0]["nearest_header_hint_unverified"])

    def test_rejects_nonempty_region_label(self):
        with self.assertRaisesRegex(ValueError, "empty text"):
            scoped_column_hints([], [], [box("table", 0, 0, 10, 10)])

    def test_rejects_invalid_region_coordinates(self):
        with self.assertRaises(ValueError):
            scoped_column_hints([], [], [box("", 0, 0, float("nan"), 10)])


if __name__ == "__main__":
    unittest.main()
