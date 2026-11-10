# Chronological out-of-sample paper evaluation (T07 foundation)

`scripts.sma_out_of_sample.evaluate_sma_out_of_sample` evaluates one caller-fixed
SMA window with explicit `train_end` and `test_start` ISO dates. It performs no
search, fitting, ranking or parameter selection. The caller must choose the
window and split before inspecting test results; this code cannot determine
whether the caller already selected them using that information.

```python
from scripts.sma_out_of_sample import evaluate_sma_out_of_sample

evaluation = evaluate_sma_out_of_sample(
    snapshot,
    evidence_as_of="2026-11-06T16:00:00+08:00",
    expected_adjustment="unadjusted",
    train_end="2026-11-04",
    test_start="2026-11-05",
    window=2,
    initial_cash=10000,
    board_lot_size=100,
    commission_bps=3,
    minimum_fee=5,
    sell_tax_bps=5,
    slippage_bps=10,
)
```

Both dates must identify observed bars, `train_end < test_start`, and test must
immediately follow train in the supplied observations. No observed row may be
left unassigned between them. This does not require consecutive calendar dates
or prove that no market sessions are missing. Training must contain at least
`window` observations. The entire snapshot and evidence cutoff are validated;
no future evidence is silently dropped. The 2000-bar simulator bound applies.

The training run is diagnostic, using all bars through `train_end`. The test run
starts with a separate fresh `initial_cash` and zero shares. Only the last
`window` training bars are prepended as signal warmup. They produce no test
fills, fees, skips or equity marks, and no training position, cash balance or
return is carried into the test account. The first test open may execute a
known prior training-close signal. Each later test open uses only the previous
observed close signal. Thus warmup is used without including training profit
in test return. Test returns start from the declared initial cash at the first
test open, including any first-open fee/slippage. A one-bar test is allowed.

The paper simulator now has an optional `execution_start_date` argument. When
omitted, existing behavior is preserved. When supplied, it must be an observed
bar date; earlier data supplies signals only and the result's daily marks start
at that date. All signal records, including warmup, remain in the result for
audit. This is an execution gate, not a historical data-availability cutoff.

Train and test share the same explicit costs, slippage and lot assumptions.
Only unadjusted prices are accepted. Final positions remain marked at the
segment's final close, with no forced liquidation or implicit exit fee. The
returned experimental total returns are hypothetical, not verified performance
or an investment recommendation. There is no buy-and-hold benchmark,
annualization, Sharpe ratio, optimization or walk-forward re-fitting in this
first evaluator. T07 remains incomplete.

Historical point-in-time and source verification remain false. Current snapshots
are not proof of availability at simulated dates. Trading calendars, corporate
actions, dividends, price limits, suspensions and liquidity/partial fills remain
unmodeled, as described in [sma-paper-backtest.md](sma-paper-backtest.md).

```sh
python -m unittest tests.test_sma_paper_backtest tests.test_sma_out_of_sample -v
```
