import copy
import unittest

from scripts.sma_out_of_sample import evaluate_sma_out_of_sample
from scripts.sma_paper_backtest import run_sma_paper_backtest


def snapshot():
    rows = []
    for day, value in (("2026-11-02", 10), ("2026-11-03", 20), ("2026-11-04", 30),
                       ("2026-11-05", 5), ("2026-11-06", 10)):
        rows.append(dict(date=day, open=value, high=value, low=value, close=value, volume=10000))
    return dict(schema_version="0.1", symbol="000776.SZ", source="akshare", upstream="eastmoney",
                interface="stock_zh_a_hist", adjust="", price_unit="CNY_per_share",
                volume_unit="lots_100_shares", start_date="2026-11-02", end_date="2026-11-06",
                retrieved_at="2026-11-06T16:00:00+08:00", source_content_verified=False,
                historical_point_in_time_verified=False, records=rows)


def settings():
    return dict(evidence_as_of="2026-11-06T16:00:00+08:00", expected_adjustment="unadjusted",
                window=2, initial_cash=10000, board_lot_size=100, commission_bps=0,
                minimum_fee=0, sell_tax_bps=0, slippage_bps=0)


def evaluate(data=None, **changes):
    options = dict(**settings(), train_end="2026-11-04", test_start="2026-11-05")
    options.update(changes)
    return evaluate_sma_out_of_sample(snapshot() if data is None else data, **options)


class OutOfSampleTests(unittest.TestCase):
    def test_test_account_is_fresh_and_first_open_uses_prior_training_signal(self):
        result = evaluate()
        train, test = result["train"], result["test"]
        self.assertEqual(train["final_shares"], 300)
        self.assertEqual(test["initial_cash"], 10000)
        self.assertEqual(test["fills"][0]["quantity"], 2000)
        self.assertEqual(test["fills"][0]["signal_date"], "2026-11-04")
        self.assertEqual(test["fills"][0]["date"], "2026-11-05")
        self.assertEqual([mark["date"] for mark in test["marks"]], ["2026-11-05", "2026-11-06"])
        self.assertTrue(all(fill["date"] >= result["test_start"] for fill in test["fills"]))
        self.assertEqual(test["marks"][0]["equity"], 10000)
        self.assertEqual(test["experimental_total_return"], 1)

    def test_test_values_do_not_change_training_or_first_open_order(self):
        data = snapshot()
        changed = copy.deepcopy(data)
        changed["records"][3].update(high=500, close=500)
        first, second = evaluate(data), evaluate(changed)
        self.assertEqual(first["train"], second["train"])
        self.assertEqual(first["test"]["fills"][0], second["test"]["fills"][0])
        self.assertEqual(first["fixed_window"], second["fixed_window"])
        self.assertEqual(first["parameter_policy"], "caller_fixed_window_no_search")

    def test_warmup_does_not_trade_or_charge_fees(self):
        result = evaluate(minimum_fee=5)
        test = result["test"]
        self.assertEqual(result["test_warmup_dates"], ["2026-11-03", "2026-11-04"])
        self.assertEqual(test["fills"][0]["quantity"], 1900)
        self.assertEqual(test["fills"][0]["cash_after"], 495)
        self.assertEqual(test["total_commission"], 10)
        self.assertEqual(len(test["marks"]), result["test_bar_count"])

    def test_single_test_bar_is_marked_without_forced_exit(self):
        result = evaluate(train_end="2026-11-05", test_start="2026-11-06")
        self.assertEqual(len(result["test"]["marks"]), 1)
        self.assertTrue(result["test"]["last_signal_has_no_next_bar"])
        self.assertFalse(result["test"]["assumptions"]["forced_liquidation"])

    def test_split_dates_must_be_observed_ordered_and_adjacent(self):
        for changes in (dict(train_end="2026-11-05", test_start="2026-11-04"),
                        dict(train_end="2026-11-04", test_start="2026-11-04"),
                        dict(train_end="2026-11-01"), dict(test_start="2026-11-07"),
                        dict(train_end="2026-11-03", test_start="2026-11-05")):
            with self.subTest(changes=changes), self.assertRaises(ValueError):
                evaluate(**changes)

    def test_requires_sufficient_training_for_the_explicit_window(self):
        for window in (True, 0, 4, 2001):
            with self.subTest(window=window), self.assertRaises(ValueError):
                evaluate(window=window)

    def test_rejects_adjusted_snapshot_and_future_evidence(self):
        with self.assertRaises(ValueError):
            evaluate(expected_adjustment="forward_adjusted")
        data = snapshot()
        data["adjust"] = "qfq"
        with self.assertRaises(ValueError):
            evaluate(data)
        with self.assertRaises(ValueError):
            evaluate(evidence_as_of="2026-11-05T16:00:00+08:00")

    def test_default_simulator_behavior_remains_unchanged(self):
        data = snapshot()
        default = run_sma_paper_backtest(data, **settings())
        explicit = run_sma_paper_backtest(data, execution_start_date=data["start_date"], **settings())
        for key in ("fills", "marks", "signals", "final_cash", "final_shares", "experimental_total_return"):
            self.assertEqual(default[key], explicit[key])

    def test_no_mutation_or_verified_performance_claim(self):
        data = snapshot()
        before = copy.deepcopy(data)
        result = evaluate(data)
        self.assertEqual(data, before)
        self.assertFalse(result["historical_point_in_time_verified"])
        self.assertFalse(result["test"]["source_content_verified"])
