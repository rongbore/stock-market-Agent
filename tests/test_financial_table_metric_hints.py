import unittest
from scripts.financial_table_metric_hints import table_metric_hints


def cell(text, row, col, x0, x1, table=0):
    return dict(page=1, table_index=table, row_index=row, column_index=col,
                text=text, bbox=[x0, row * 20, x1, row * 20 + 10])


class MetricHintTests(unittest.TestCase):
    def test_explicit_label_and_unit(self):
        rows = [cell("年初至报告期末", 0, 1, 50, 100),
                cell("营业总收入（万元）", 1, 0, 0, 45), cell("123.45", 1, 1, 60, 90)]
        c = table_metric_hints(rows)["candidates"][0]
        self.assertEqual((c["metric_hint_unverified"], c["unit_hint_unverified"],
                          c["period_hint_unverified"]), ("revenue", "CNY_10000", "year_to_date"))
        self.assertFalse(c["value_verified"])

    def test_split_cash_flow_label_preserves_both_fragments(self):
        rows = [cell("经营活动产生的现金流量净", 1, 0, 0, 45),
                cell("-8,137.59", 1, 1, 60, 90), cell("额（元）", 2, 0, 0, 45)]
        c = table_metric_hints(rows)["candidates"][0]
        self.assertEqual(c["metric_hint_unverified"], "operating_cash_flow")
        self.assertEqual(len(c["label_cells"]), 2)

    def test_does_not_cross_another_data_row(self):
        rows = [cell("经营活动产生的现金流量净", 1, 0, 0, 45), cell("1", 1, 1, 60, 90),
                cell("额（元）", 2, 0, 0, 45), cell("2", 2, 1, 60, 90)]
        self.assertIsNone(table_metric_hints(rows)["candidates"][0]["metric_hint_unverified"])

    def test_missing_unit_or_other_table_label_does_not_assign(self):
        for label in (cell("总资产", 1, 0, 0, 45), cell("总资产（元）", 1, 0, 0, 45, table=1)):
            c = table_metric_hints([label, cell("1", 1, 1, 60, 90)])["candidates"][0]
            self.assertIsNone(c["metric_hint_unverified"])
