# Buy-and-hold comparison and nonannualized paper risk metrics

The chronological SMA evaluator now adds a buy-and-hold benchmark over exactly
the same test bars, starting from the same initial cash and zero shares. It uses
the same explicit board lot, commission bps, minimum fee, sell-tax bps and
slippage bps. Shared execution code calculates affordability, fees, slippage,
cash and equity for both strategies; there is no separate benchmark fee formula.

The benchmark is a fixed decision declared before the first test open. It makes
one purchase attempt at that observed open, buying the maximum affordable whole
board lots including commission. Its fill has `signal_date=null`, distinguishing
the predeclared decision from an SMA close-based signal. A first-open zero-volume
bar or unaffordable lot leaves the account in cash; there is no later retry or
rebalance. This deliberately avoids inventing an execution date. It does not
prove that the first open was tradable. No sale is forced at test end, so the
sell-tax assumption is shared but no sell tax is charged to an unsold position.
Final equity includes hypothetical remaining shares marked at the last close.

`run_buy_and_hold_paper_backtest` also accepts a raw snapshot directly, with all
the usual explicit evidence, adjustment, capital, lot and cost arguments except
the SMA window. Only unadjusted prices are accepted. The chronological evaluator
passes only test observations to it, with no training marks, positions or fees.
Its `signals` entries have null signal dates and target 1 to describe the fixed
holding policy; only the first entry can trigger a purchase attempt.

`scripts.paper_risk_metrics.paper_risk_metrics(run)` consumes the hypothetical
daily equity marks and initial cash, producing:

| Field | Exact definition |
| --- | --- |
| `observed_period_return` | Last marked equity / initial cash - 1, including simulated trading costs and unrealized final value |
| `max_drawdown_fraction` | Largest `(running_peak - marked_equity) / running_peak`, with initial cash included as a peak before the first mark |
| `max_drawdown_peak_date` | Date of the observed peak responsible for the worst drawdown; null when that peak is initial capital, or when drawdown is zero |
| `max_drawdown_trough_date` | Observed trough date of the first worst drawdown; null when drawdown is zero |
| `observed_mark_count` | Number of provided daily marks, not a verified trading-session count |

The initial-capital peak makes an immediate first-day price loss, commission or
slippage visible in drawdown even if later marks rise. A total marked loss gives
drawdown 1; zero marked equity never becomes a divisor. No intraday highs/lows
are used for risk measurement, so intraday drawdown is not measured. Inputs must
be a nonempty ascending unique sequence of at most 2000 marks, finite nonnegative
equity at most 1e30, finite initial cash 0.01 to 1e15, and last marked equity must
match the declared final marked equity. Decimal arithmetic is used for ratios;
reported values are floats based on already serialized paper marks.

`comparison.arithmetic_return_difference` is **SMA test observed return minus
benchmark observed return**. The values are fractions: `0.05` means five
percentage points. It is not `(1 + SMA return) / (1 + benchmark return) - 1`, a
geometric relative return, or an alpha measure. Comparison remains defined when
a benchmark has zero final equity because no benchmark-return ratio is used.

There is no annualization, Sharpe ratio, volatility model, parameter search or
claim of statistical significance or profitability. These are simplified paper
calculations, not verified investment performance or a recommendation.
Historical point-in-time/source flags remain false. Exchange-calendar gaps,
corporate actions, dividends, price limits, suspensions, liquidity, partial fills,
auction availability and broker settlement rounding remain outside the model.

```sh
python -m unittest tests.test_sma_paper_backtest tests.test_sma_out_of_sample tests.test_paper_benchmark_risk -v
```
