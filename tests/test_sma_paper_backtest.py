import copy
import unittest

from scripts.sma_paper_backtest import run_sma_paper_backtest


def snapshot():
    rows = []
    for day, op, close in (("2026-11-02", 10, 10), ("2026-11-03", 12, 12),
                            ("2026-11-04", 10, 8), ("2026-11-05", 9, 8)):
        rows.append(dict(date=day, open=op, high=max(op, close), low=min(op, close),
                         close=close, volume=10000))
    return dict(schema_version="0.1", symbol="000776.SZ", source="akshare", upstream="eastmoney",
                interface="stock_zh_a_hist", adjust="", price_unit="CNY_per_share",
                volume_unit="lots_100_shares", start_date="2026-11-02", end_date="2026-11-05",
                retrieved_at="2026-11-05T16:00:00+08:00", source_content_verified=False,
                historical_point_in_time_verified=False, records=rows)


def run(data=None, **changes):
    options = dict(evidence_as_of="2026-11-05T16:00:00+08:00", expected_adjustment="unadjusted",
                   window=2, initial_cash=10000, board_lot_size=100, commission_bps=0,
                   minimum_fee=0, sell_tax_bps=0, slippage_bps=0)
    options.update(changes)
    return run_sma_paper_backtest(snapshot() if data is None else data, **options)


class SmaPaperBacktestTests(unittest.TestCase):
    def test_signals_fill_at_next_open_and_final_holdings_are_marked(self):
        data = snapshot()
        data["records"] = data["records"][:3]
        data["end_date"] = "2026-11-04"
        result = run(data)
        self.assertEqual(len(result["fills"]), 1)
        fill = result["fills"][0]
        self.assertEqual((fill["signal_date"], fill["date"], fill["execution_price"]),
                         ("2026-11-03", "2026-11-04", 10))
        self.assertEqual(result["final_shares"], 1000)
        self.assertEqual(result["final_marked_equity"], 8000)
        self.assertAlmostEqual(result["experimental_total_return"], -0.2)
        self.assertTrue(result["last_signal_has_no_next_bar"])
        self.assertFalse(result["assumptions"]["forced_liquidation"])

    def test_future_close_does_not_change_prior_signal_or_same_day_open_fill(self):
        before = snapshot()
        after = copy.deepcopy(before)
        after["records"][2].update(close=100, high=100)
        first, second = run(before), run(after)
        self.assertEqual(first["signals"][:2], second["signals"][:2])
        self.assertEqual(first["fills"][0], second["fills"][0])

    def test_commission_slippage_sell_tax_and_lot_affordability(self):
        result = run(minimum_fee=5, sell_tax_bps=10, slippage_bps=100)
        buy, sell = result["fills"]
        self.assertEqual(buy["quantity"], 900)
        self.assertAlmostEqual(buy["execution_price"], 10.1)
        self.assertAlmostEqual(buy["cash_after"], 905)
        self.assertAlmostEqual(sell["execution_price"], 8.91)
        self.assertAlmostEqual(sell["sell_tax"], 8.019)
        self.assertAlmostEqual(result["final_cash"], 8910.981)
        self.assertEqual(result["total_commission"], 10)
        self.assertAlmostEqual(result["total_slippage_cost"], 171)
        self.assertTrue(all(mark["cash"] >= 0 and mark["shares"] % 100 == 0
                            for mark in result["marks"]))

    def test_proportional_commission_is_included_in_buy_affordability(self):
        result = run(commission_bps=100)
        self.assertEqual(result["fills"][0]["quantity"], 900)
        self.assertEqual(result["fills"][0]["commission"], 90)
        self.assertEqual(result["fills"][0]["cash_after"], 910)

    def test_insufficient_history_or_no_next_bar_produces_no_fill(self):
        for window in (4, 5):
            result = run(window=window)
            self.assertEqual(result["fills"], [])
            self.assertEqual(result["final_marked_equity"], 10000)
        self.assertEqual(run(initial_cash=10)["fills"], [])
        self.assertIn("no_affordable_lot", [s["reason"] for s in run(initial_cash=10)["skipped"]])

    def test_zero_volume_and_unaffordable_sell_fee_cannot_create_negative_cash(self):
        data = snapshot()
        data["records"][2]["volume"] = 0
        result = run(data)
        self.assertEqual(result["fills"], [])
        self.assertEqual(result["skipped"][0]["reason"], "zero_reported_volume")
        data = snapshot()
        data["records"][3].update(open=0.000001, low=0.000001, close=0.000001)
        result = run(data, minimum_fee=5000)
        self.assertEqual(len(result["fills"]), 1)
        self.assertEqual(result["skipped"][-1]["reason"], "unaffordable_sell_fees")
        self.assertGreaterEqual(result["final_cash"], 0)

    def test_rejects_invalid_settings_and_adjusted_data(self):
        for changes in (dict(window=True), dict(window=2001), dict(initial_cash=0),
                        dict(initial_cash=float("inf")), dict(board_lot_size=1.5),
                        dict(commission_bps=-1), dict(minimum_fee=True), dict(sell_tax_bps=1001),
                        dict(slippage_bps=float("nan")), dict(expected_adjustment="forward_adjusted")):
            with self.subTest(changes=changes), self.assertRaises(ValueError):
                run(**changes)
        data = snapshot()
        data["adjust"] = "qfq"
        with self.assertRaises(ValueError):
            run(data)

    def test_bounded_prices_reject_extreme_but_otherwise_structural_data(self):
        data = snapshot()
        data["records"][0].update(open=1e100, high=1e100, low=1e100, close=1e100)
        with self.assertRaisesRegex(ValueError, "supported range"):
            run(data)

    def test_source_is_not_mutated_and_verification_is_not_promoted(self):
        data = snapshot()
        original = copy.deepcopy(data)
        result = run(data)
        self.assertEqual(data, original)
        self.assertFalse(result["historical_point_in_time_verified"])
        self.assertFalse(result["exchange_calendar_checked"])
