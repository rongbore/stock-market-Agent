"""Fixed-parameter chronological SMA evaluation; no parameter search or PIT proof."""
from scripts.backtest_data_contract import _day, build_backtest_dataset
from scripts.sma_paper_backtest import MAX_BARS, run_sma_paper_backtest


def evaluate_sma_out_of_sample(snapshot, *, evidence_as_of, expected_adjustment,
                               train_end, test_start, window, initial_cash,
                               board_lot_size, commission_bps, minimum_fee,
                               sell_tax_bps, slippage_bps):
    """Return independent train/test paper runs for one caller-fixed SMA window.

    The split must assign every observed bar to train or test. Trailing training
    closes warm up the test; training trades never seed test holdings or cash.
    """
    if expected_adjustment != "unadjusted":
        raise ValueError("out-of-sample evaluation supports unadjusted bars only")
    if type(window) is not int or not 1 <= window <= MAX_BARS:
        raise ValueError("window must be 1 to 2000")
    end = _day(train_end).isoformat()
    start = _day(test_start).isoformat()
    if end >= start:
        raise ValueError("train_end must precede test_start")
    dataset = build_backtest_dataset(snapshot, evidence_as_of=evidence_as_of,
                                     expected_adjustment=expected_adjustment)
    bars = dataset["bars"]
    if len(bars) > MAX_BARS:
        raise ValueError("evaluation limited to 2000 bars")
    dates = [bar["date"] for bar in bars]
    if end not in dates or start not in dates:
        raise ValueError("split dates must identify observed bars")
    boundary, first_test = dates.index(end), dates.index(start)
    if first_test != boundary + 1:
        raise ValueError("split must not leave unassigned observed bars")
    if boundary + 1 < window:
        raise ValueError("insufficient training history for fixed SMA window")

    def subset(rows):
        return {**snapshot, "start_date": rows[0]["date"], "end_date": rows[-1]["date"],
                "records": [dict(row) for row in rows]}

    # Copy raw rows, since the simulator performs its own unit normalization.
    raw = snapshot["records"]
    train_snapshot = subset(raw[:first_test])
    warmup = raw[first_test - window:first_test]
    test_snapshot = subset(warmup + raw[first_test:])
    settings = dict(evidence_as_of=evidence_as_of, expected_adjustment=expected_adjustment,
                    window=window, initial_cash=initial_cash, board_lot_size=board_lot_size,
                    commission_bps=commission_bps, minimum_fee=minimum_fee,
                    sell_tax_bps=sell_tax_bps, slippage_bps=slippage_bps)
    train = run_sma_paper_backtest(train_snapshot, **settings)
    test = run_sma_paper_backtest(test_snapshot, execution_start_date=start, **settings)
    return {
        "schema_version": "0.1", "symbol": dataset["symbol"],
        "status": "EXPERIMENTAL_CHRONOLOGICAL_EVALUATION_UNVERIFIED",
        "parameter_policy": "caller_fixed_window_no_search",
        "fixed_window": window, "train_end": end, "test_start": start,
        "train_bar_count": first_test, "test_bar_count": len(bars) - first_test,
        "test_warmup_dates": [row["date"] for row in warmup],
        "test_account_policy": "fresh_cash_no_train_positions",
        "train": train, "test": test,
        "source_content_verified": False, "historical_point_in_time_verified": False,
        "exchange_calendar_checked": False,
        "limitations": [
            "Caller fixes dates and window; prior test-informed selection cannot be detected.",
            "Test warmup uses training closes only; no training trades or returns are carried.",
            "First test open may execute the last training close signal.",
            "No parameter optimization, buy-and-hold benchmark or risk-adjusted metrics.",
            "Observed chronological separation is not proof of historical availability.",
            "Both runs retain the paper simulator's simplified execution and fee assumptions.",
        ],
    }
