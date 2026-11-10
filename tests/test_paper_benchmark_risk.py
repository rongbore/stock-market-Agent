import copy
import math
import unittest

from scripts.paper_risk_metrics import paper_risk_metrics
from scripts.sma_paper_backtest import run_buy_and_hold_paper_backtest
from tests.test_sma_out_of_sample import evaluate, settings, snapshot


def benchmark(data=None, **changes):
    data = snapshot() if data is None else data
    options = {key: value for key, value in settings().items() if key != "window"}
    options.update(changes)
    return run_buy_and_hold_paper_backtest(data, **options)


class BenchmarkRiskTests(unittest.TestCase):
    def test_comparison_has_identical_interval_initial_cash_and_cost_assumptions(self):
        result = evaluate(commission_bps=100, minimum_fee=5, sell_tax_bps=50, slippage_bps=100)
        sma, hold = result["test"], result["benchmark"]
        self.assertEqual([m["date"] for m in sma["marks"]], [m["date"] for m in hold["marks"]])
        self.assertEqual(hold["fills"][0]["date"], result["test_start"])
        for key in ("initial_cash", "board_lot_size", "commission_bps", "minimum_fee",
                    "sell_tax_bps", "slippage_bps", "adjustment", "forced_liquidation"):
            self.assertEqual(sma["assumptions"][key], hold["assumptions"][key])
        for key in ("quantity", "execution_price", "notional", "commission", "cash_after"):
            self.assertEqual(sma["fills"][0][key], hold["fills"][0][key])
        self.assertEqual(hold["fills"][0]["signal_date"], None)
        self.assertEqual(len(hold["fills"]), 1)
        self.assertEqual(hold["final_shares"], 1900)
        self.assertAlmostEqual(hold["final_marked_equity"], 19309.05)
        self.assertEqual(hold["total_sell_tax"], 0)
        self.assertFalse(hold["assumptions"]["forced_liquidation"])
        expected = (result["metrics"]["test"]["observed_period_return"]
                    - result["metrics"]["benchmark"]["observed_period_return"])
        self.assertEqual(result["comparison"]["arithmetic_return_difference"], expected)
        self.assertFalse(result["comparison"]["verified_performance"])

    def test_first_day_loss_counts_from_initial_capital(self):
        data = snapshot()
        data["records"] = [dict(date="2026-11-02", open=10, high=10, low=8, close=8, volume=10000)]
        data["end_date"] = "2026-11-02"
        hold = benchmark(data)
        metrics = paper_risk_metrics(hold)
        self.assertEqual(hold["fills"][0]["date"], "2026-11-02")
        self.assertAlmostEqual(metrics["observed_period_return"], -0.2)
        self.assertAlmostEqual(metrics["max_drawdown_fraction"], 0.2)
        self.assertIsNone(metrics["max_drawdown_peak_date"])
        self.assertEqual(metrics["max_drawdown_trough_date"], "2026-11-02")
        self.assertFalse(metrics["annualized"])
        self.assertFalse(metrics["verified_performance"])

    def test_fee_and_slippage_loss_counts_in_first_day_drawdown(self):
        data = snapshot()
        data["records"] = data["records"][:1]
        data["end_date"] = "2026-11-02"
        result = benchmark(data, minimum_fee=5, slippage_bps=100)
        metrics = paper_risk_metrics(result)
        self.assertEqual(result["fills"][0]["quantity"], 900)
        self.assertEqual(result["final_cash"], 905)
        self.assertEqual(result["final_marked_equity"], 9905)
        self.assertAlmostEqual(metrics["max_drawdown_fraction"], 0.0095)

    def test_zero_volume_first_open_is_skipped_without_later_retry(self):
        data = snapshot()
        data["records"][3]["volume"] = 0
        result = evaluate(data)["benchmark"]
        self.assertEqual(result["fills"], [])
        self.assertEqual(result["skipped"], [{"signal_date": None, "date": "2026-11-05",
                                             "reason": "zero_reported_volume"}])
        self.assertEqual(result["final_marked_equity"], result["initial_cash"])
        self.assertEqual(paper_risk_metrics(result)["max_drawdown_fraction"], 0)

    def test_unaffordable_first_lot_is_not_borrowed(self):
        result = evaluate(initial_cash=10)["benchmark"]
        self.assertEqual(result["fills"], [])
        self.assertEqual(result["final_cash"], 10)
        self.assertEqual(result["final_shares"], 0)
        self.assertEqual(result["skipped"][0]["reason"], "no_affordable_lot")

    def test_max_drawdown_tracks_observed_peak_and_later_trough(self):
        run = dict(initial_cash=100, final_marked_equity=110,
                   marks=[dict(date="2026-11-02", equity=120),
                          dict(date="2026-11-03", equity=60),
                          dict(date="2026-11-04", equity=110)])
        metrics = paper_risk_metrics(run)
        self.assertEqual(metrics["max_drawdown_fraction"], 0.5)
        self.assertEqual(metrics["max_drawdown_peak_date"], "2026-11-02")
        self.assertEqual(metrics["max_drawdown_trough_date"], "2026-11-03")
        self.assertEqual(metrics["observed_period_return"], 0.1)

    def test_metrics_reject_nonfinite_unbounded_or_inconsistent_equity(self):
        baseline = dict(initial_cash=100, final_marked_equity=100,
                        marks=[dict(date="2026-11-02", equity=100)])
        for equity in (-1, True, float("nan"), float("inf"), 1e31, 10 ** 1000):
            data = copy.deepcopy(baseline)
            data["marks"][0]["equity"] = equity
            data["final_marked_equity"] = equity
            with self.subTest(equity=str(equity)[:40]), self.assertRaises(ValueError):
                paper_risk_metrics(data)
        data = copy.deepcopy(baseline)
        data["final_marked_equity"] = 101
        with self.assertRaisesRegex(ValueError, "differs"):
            paper_risk_metrics(data)
        data = copy.deepcopy(baseline)
        data["marks"] *= 2
        with self.assertRaisesRegex(ValueError, "ascending"):
            paper_risk_metrics(data)

    def test_extreme_supported_metrics_stay_finite_including_total_loss(self):
        run = dict(initial_cash=0.01, final_marked_equity=1e30,
                   marks=[dict(date="2026-11-02", equity=1e30)])
        result = paper_risk_metrics(run)
        self.assertTrue(math.isfinite(result["observed_period_return"]))
        self.assertEqual(result["max_drawdown_fraction"], 0)
        run["marks"].append(dict(date="2026-11-03", equity=0))
        run["final_marked_equity"] = 0
        self.assertEqual(paper_risk_metrics(run)["max_drawdown_fraction"], 1)

    def test_benchmark_preserves_input_and_rejects_adjusted_or_invalid_costs(self):
        data = snapshot()
        original = copy.deepcopy(data)
        benchmark(data)
        self.assertEqual(data, original)
        for changes in (dict(expected_adjustment="forward_adjusted"), dict(minimum_fee=-1),
                        dict(slippage_bps=float("nan")), dict(board_lot_size=True)):
            with self.subTest(changes=changes), self.assertRaises(ValueError):
                benchmark(**changes)
