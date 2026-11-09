import copy
import unittest

from scripts.backtest_data_contract import build_backtest_dataset


def snapshot():
    return {"schema_version": "0.1", "symbol": "000776.SZ", "source": "akshare",
            "upstream": "eastmoney", "interface": "stock_zh_a_hist", "adjust": "",
            "price_unit": "CNY_per_share", "volume_unit": "lots_100_shares",
            "start_date": "2026-11-02", "end_date": "2026-11-03",
            "retrieved_at": "2026-11-03T16:00:00+08:00", "source_content_verified": False,
            "historical_point_in_time_verified": False,
            "records": [{"date": "2026-11-02", "open": 10, "high": 12, "low": 9,
                         "close": 11, "volume": 25},
                        {"date": "2026-11-03", "open": 11, "high": 12, "low": 10,
                         "close": 10, "volume": 0}]}


def build(data=None, **kwargs):
    return build_backtest_dataset(data if data is not None else snapshot(),
                                  evidence_as_of=kwargs.pop("evidence_as_of", "2026-11-03T08:00:00Z"),
                                  expected_adjustment=kwargs.pop("expected_adjustment", "unadjusted"), **kwargs)


class BacktestDataTests(unittest.TestCase):
    def test_normalizes_lots_without_mutation_or_verified_claims(self):
        data = snapshot()
        before = copy.deepcopy(data)
        result = build(data)
        self.assertEqual(result["bars"][0]["volume"], 2500)
        self.assertEqual(result["bars"][1]["volume"], 0)
        self.assertEqual(data, before)
        self.assertFalse(result["historical_point_in_time_verified"])
        self.assertFalse(result["exchange_calendar_checked"])

    def test_sina_shares_are_not_multiplied(self):
        data = snapshot()
        data.update(upstream="sina", interface="stock_zh_a_daily", volume_unit="shares")
        self.assertEqual(build(data)["bars"][0]["volume"], 25)

    def test_adjustment_is_explicit_and_must_match(self):
        data = snapshot()
        data["adjust"] = "qfq"
        with self.assertRaisesRegex(ValueError, "adjustment mismatch"):
            build(data)
        result = build(data, expected_adjustment="forward_adjusted")
        self.assertEqual(result["adjustment"], "forward_adjusted")
        for assumption in (None, "unknown", ""):
            with self.subTest(assumption=assumption), self.assertRaises(ValueError):
                build(expected_adjustment=assumption)

    def test_rejects_duplicate_unsorted_and_out_of_range_dates(self):
        for mode in ("duplicate", "reverse", "outside", "weekend"):
            data = snapshot()
            if mode == "duplicate":
                data["records"][1]["date"] = "2026-11-02"
            elif mode == "reverse":
                data["records"].reverse()
            elif mode == "outside":
                data["records"][0]["date"] = "2026-10-30"
            else:
                data["records"][0]["date"] = "2026-11-01"
                data["start_date"] = "2026-11-01"
            with self.subTest(mode=mode), self.assertRaises(ValueError):
                build(data)

    def test_rejects_bad_numeric_types_ranges_and_relationships(self):
        cases = [("open", True), ("close", "11"), ("high", float("nan")),
                 ("volume", float("inf")), ("low", 0), ("volume", -1),
                 ("low", 11), ("high", 10), ("volume", 1e308)]
        for key, value in cases:
            data = snapshot()
            data["records"][0][key] = value
            with self.subTest(key=key, value=value), self.assertRaises(ValueError):
                build(data)

    def test_rejects_unknown_units_source_flags_and_extra_bar_fields(self):
        for key, value in (("volume_unit", "unknown"), ("price_unit", "USD"),
                           ("interface", "unknown"), ("source_content_verified", True),
                           ("historical_point_in_time_verified", None)):
            data = snapshot()
            data[key] = value
            with self.subTest(key=key), self.assertRaises(ValueError):
                build(data)
        data = snapshot()
        data["records"][0]["adjusted_close"] = 12
        with self.assertRaises(ValueError):
            build(data)

    def test_rejects_future_retrieval_naive_cutoff_and_incomplete_daily_bar(self):
        with self.assertRaisesRegex(ValueError, "retrieved after"):
            build(evidence_as_of="2026-11-03T07:59:59Z")
        with self.assertRaisesRegex(ValueError, "timezone"):
            build(evidence_as_of="2026-11-03T16:00:00")
        data = snapshot()
        data["retrieved_at"] = "2026-11-03T14:59:59+08:00"
        with self.assertRaisesRegex(ValueError, "bar closes after"):
            build(data)

    def test_accepts_close_boundary_with_equivalent_utc_cutoff(self):
        data = snapshot()
        data["retrieved_at"] = "2026-11-03T15:00:00+08:00"
        self.assertEqual(len(build(data, evidence_as_of="2026-11-03T07:00:00Z")["bars"]), 2)
