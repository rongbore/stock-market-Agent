import unittest
from scripts.financial_table_period_hints import table_period_hints


def cell(text, row, column, x0, x1, table=0):
    return dict(page=1, table_index=table, row_index=row, column_index=column,
                text=text, bbox=[x0, row * 20, x1, row * 20 + 10])


class PeriodHintTests(unittest.TestCase):
    def test_quarter_and_cumulative_columns(self):
        result = table_period_hints([cell("本报告期", 0, 0, 0, 50),
                                    cell("年初至报告期末", 0, 1, 50, 100),
                                    cell("-10.00", 1, 0, 10, 40), cell("-", 1, 1, 50, 60),
                                    cell("1,000.00", 1, 2, 60, 90)])
        self.assertEqual([c["period_hint_unverified"] for c in result["candidates"]],
                         ["current_quarter", "year_to_date"])
        self.assertFalse(result["column_ownership_verified"])

    def test_new_header_block_stops_old_cumulative_hint(self):
        result = table_period_hints([cell("年初至报告期末", 0, 0, 0, 100),
                                    cell("本报告期末", 2, 0, 0, 50),
                                    cell("1", 3, 0, 60, 90)])
        self.assertIsNone(result["candidates"][0]["period_hint_unverified"])

    def test_other_table_and_overlapping_headers_do_not_assign(self):
        for headers in ([cell("本报告期", 0, 0, 0, 100, table=1)],
                        [cell("本报告期", 0, 0, 0, 100), cell("本报告期末", 0, 1, 0, 100)]):
            self.assertIsNone(table_period_hints(headers + [cell("1", 1, 0, 10, 20)])
                              ["candidates"][0]["period_hint_unverified"])

    def test_duplicate_positions_rejected(self):
        c = cell("1", 0, 0, 0, 10)
        with self.assertRaises(ValueError):
            table_period_hints([c, c])
