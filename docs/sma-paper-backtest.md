# Experimental offline SMA paper backtest

`scripts.sma_paper_backtest.run_sma_paper_backtest` adds a bounded, deterministic
single-symbol paper simulation to the T06 data/signal branch (PR #244, dependent
on the data contract in PR #241). It makes no network, model or brokerage calls.

```python
from scripts.sma_paper_backtest import run_sma_paper_backtest

result = run_sma_paper_backtest(
    snapshot,
    evidence_as_of="2026-11-05T16:00:00+08:00",
    expected_adjustment="unadjusted",
    window=20,
    initial_cash=100000,
    board_lot_size=100,
    commission_bps=3,
    minimum_fee=5,
    sell_tax_bps=5,
    slippage_bps=10,
)
```

Every setting is mandatory and an explicit experiment assumption, not an inferred
broker/exchange rule. Only unadjusted data is accepted: adjusted bars are rejected
until corporate-action accounting is implemented. Daily data is validated once.
The reusable `sma_schedule` creates causal close-based targets; warm-up days have
no target. Close strictly above its trailing SMA targets 1, otherwise 0. A target
can affect holdings only at the next observed bar's open; the last target never
executes without a later bar. There is no same-close fill. Missing sessions are
not invented, so the next observed bar may not be the next exchange session.

When flat and target 1, buy the maximum affordable integer number of board lots.
When invested and target 0, sell the full board-lot holding. A continued target 1
does not add to an existing position. Buy slippage raises the observed open and
sell slippage lowers it. Each executed side pays the larger of the configured
minimum fee or notional times commission bps / 10000; sells additionally pay
notional times sell-tax bps / 10000. Slippage cost is reported separately and is
already reflected in the execution price, so it is not deducted a second time.
No fill occurs when the reported volume is zero, a lot is unaffordable, or a sale
would leave negative cash after fees. Such events are recorded. This is not a
liquidity/suspension model. There is no borrowing, margin or shorting.

Positions are marked at each observed close. Final holdings remain open and are
marked at the final close: there is no forced liquidation or implicit exit fee.
The experimental total return is final marked equity / initial cash - 1, including
executed fees and slippage and any unrealized final holding value. It is not
annualized and is not evidence of profitability or an investment recommendation.
The output includes signals, fills, skipped executions, daily cash/shares/equity,
commissions, sell taxes, slippage costs and explicit assumptions.

Limits: 2000 bars and SMA window at most 2000, board-lot size 1 to 1,000,000,
initial cash 0.01 to 1e15, minimum fee 0 to 1e9, each bps setting 0 to 1000,
prices 0.000001 to 1e9, and holdings at most 1e12 shares. Values must be finite
numbers; booleans are rejected. Internal accounting uses 40-digit Decimal
arithmetic without currency quantization. JSON-compatible output uses floats.
This is not an exact broker settlement/rounding model.

The same execution/accounting engine also serves
`run_buy_and_hold_paper_backtest`. That benchmark declares its purchase before
the first observed open and attempts it exactly once; it never uses a same-day
closing signal. A skipped purchase is not retried. See
[paper-benchmark-risk.md](paper-benchmark-risk.md) for interval and metric details.

No price-limit, suspension, auction, liquidity/partial-fill, exchange-calendar,
dividend, corporate-action or odd-lot model is provided. Retrieved snapshots may
not have been historically available at simulated dates. Source and historical
point-in-time verification remain false. The small-window causal schedule does
not establish a point-in-time-correct or production-ready backtest.

```sh
python -m unittest tests.test_backtest_data_contract tests.test_backtest_strategy_input tests.test_sma_paper_backtest -v
```
