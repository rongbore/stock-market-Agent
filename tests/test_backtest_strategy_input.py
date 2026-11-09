import copy
import unittest

from scripts.backtest_strategy_input import run_strategy_signal, sma_signal


def snapshot():
    return {"schema_version": "0.1", "symbol": "000776.SZ", "source": "akshare",
            "upstream": "eastmoney", "interface": "stock_zh_a_hist", "adjust": "",
            "price_unit": "CNY_per_share", "volume_unit": "lots_100_shares",
            "start_date": "2026-11-02", "end_date": "2026-11-04",
            "retrieved_at": "2026-11-04T16:00:00+08:00", "source_content_verified": False,
            "historical_point_in_time_verified": False,
            "records": [{"date": day, "open": close, "high": close, "low": close,
                         "close": close, "volume": 25}
                        for day, close in (("2026-11-02", 10), ("2026-11-03", 12),
                                           ("2026-11-04", 5))]}


def signal(data=None, **kwargs):
    options = dict(evidence_as_of="2026-11-04T16:00:00+08:00", expected_adjustment="unadjusted",
                   signal_date="2026-11-03", min_history=2, strategy=lambda context: 0.5)
    options.update(kwargs)
    return run_strategy_signal(snapshot() if data is None else data, **options)


def sma(data=None, **kwargs):
    options = dict(evidence_as_of="2026-11-04T16:00:00+08:00", expected_adjustment="unadjusted",
                   signal_date="2026-11-03", window=2)
    options.update(kwargs)
    return sma_signal(snapshot() if data is None else data, **options)


class StrategyInputTests(unittest.TestCase):
    def test_strategy_only_receives_prefix_and_normalized_units(self):
        seen = []
        def reviewer(context):
            seen.append(context)
            self.assertNotIn("requested_end", context)
            self.assertNotIn("provenance", context)
            self.assertEqual([b["date"] for b in context["bars"]], ["2026-11-02", "2026-11-03"])
            self.assertEqual(context["bars"][0]["volume"], 2500)
            self.assertEqual(context["volume_unit"], "shares")
            self.assertFalse(context["historical_point_in_time_verified"])
            return 0.5
        result = signal(strategy=reviewer)
        self.assertEqual(len(seen), 1)
        self.assertEqual(result["target_weight"], 0.5)
        self.assertEqual(result["history_count"], 2)
        self.assertFalse(result["historical_point_in_time_verified"])
        self.assertEqual(result["execution_policy"], "UNSPECIFIED_NO_FILLS")

    def test_later_bar_values_cannot_change_sma_signal(self):
        original = snapshot()
        changed = copy.deepcopy(original)
        changed["records"][-1].update(open=100000, high=100000, low=100000, close=100000)
        self.assertEqual(sma(original), sma(changed))
        self.assertEqual(sma(original)["target_weight"], 1.0)

    def test_adding_valid_future_bar_cannot_change_signal(self):
        full = snapshot()
        short = copy.deepcopy(full)
        short["records"].pop()
        short["end_date"] = "2026-11-03"
        self.assertEqual(sma(full), sma(short))

    def test_prefix_copies_are_read_only_and_input_is_not_mutated(self):
        data = snapshot()
        before = copy.deepcopy(data)
        def reviewer(context):
            with self.assertRaises(TypeError):
                context["signal_date"] = "2026-11-04"
            with self.assertRaises(TypeError):
                context["bars"][0]["close"] = 999
            return 0
        signal(data, strategy=reviewer)
        self.assertEqual(data, before)

    def test_insufficient_history_and_missing_signal_bar_do_not_call_strategy(self):
        def should_not_run(context):
            self.fail("strategy should not be invoked")
        for options in (dict(min_history=3), dict(signal_date="2026-11-05"),
                        dict(signal_date="2026-11-01")):
            with self.subTest(options=options), self.assertRaises(ValueError):
                signal(strategy=should_not_run, **options)

    def test_invalid_configuration(self):
        for value in (True, 0, -1, 1.5, 100001):
            with self.subTest(value=value), self.assertRaises(ValueError):
                sma(window=value)
            with self.subTest(value=value), self.assertRaises(ValueError):
                signal(min_history=value)
        with self.assertRaises(ValueError):
            signal(strategy=None)

    def test_invalid_target_weight(self):
        for weight in (True, "0.5", None, -0.1, 1.1, float("nan"), float("inf")):
            with self.subTest(weight=weight), self.assertRaises(ValueError):
                signal(strategy=lambda context: weight)

    def test_sma_tie_and_declining_signal_are_zero(self):
        self.assertEqual(sma(window=1)["target_weight"], 0)
        self.assertEqual(sma(signal_date="2026-11-04")["target_weight"], 0)

    def test_raw_snapshot_contract_is_revalidated(self):
        for field, value in (("volume_unit", "unknown"), ("historical_point_in_time_verified", True),
                             ("adjust", "qfq"), ("retrieved_at", "2026-11-05T16:00:00+08:00")):
            data = snapshot()
            data[field] = value
            with self.subTest(field=field), self.assertRaises(ValueError):
                signal(data)

    def test_explicit_adjusted_series_remains_unverified(self):
        data = snapshot()
        data["adjust"] = "qfq"
        result = sma(data, expected_adjustment="forward_adjusted")
        self.assertEqual(result["adjustment"], "forward_adjusted")
        self.assertFalse(result["historical_point_in_time_verified"])
