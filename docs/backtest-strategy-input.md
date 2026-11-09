# Historical-prefix strategy input (depends on PR #241)

This is the next T06 foundation on top of the offline daily-bar contract. It
produces experimental signals, not a backtest, execution plan or recommendation.

```python
from scripts.backtest_strategy_input import sma_signal

result = sma_signal(
    snapshot,
    evidence_as_of="2026-11-04T16:00:00+08:00",
    expected_adjustment="unadjusted",
    signal_date="2026-11-03",
    window=20,
)
```

The raw snapshot is revalidated with `build_backtest_dataset`. A signal date
must exactly match an observed daily bar, and the explicit window must have
enough prior observations including that bar. No calendar dates or missing
sessions are invented. The baseline uses that close and the trailing `window`
closes; target weight is 1 when close is above the SMA and 0 otherwise, including
ties. The signal is an after-close calculation and must not be interpreted as a
fill at that same close. No execution date, future opening price or next trading
session is selected.

`run_strategy_signal(..., min_history=N, strategy=callable)` also exposes a small
interface for caller-supplied strategies. The callable receives read-only copied
bars through the signal date, normalized units and unverified adjustment flags.
It receives no later bars, full dataset length, source requested end date or next
session. It must return a finite numeric long-only target weight in `[0, 1]`.
Boolean results are rejected. The callable is trusted caller code: this is not a
sandbox and cannot stop a closure from using unrelated external information.

Validation examines the full raw snapshot before evaluating the prefix. Invalid
later rows therefore block the dataset rather than being silently discarded;
changing or appending valid later bars cannot change the signal. Snapshot
retrieval/evidence cutoffs are distinct from the simulated signal date. Data
retrieved later is not thereby proven historically available. Adjusted series
may incorporate corporate actions learned later, so historical point-in-time
verification remains false even for a causal prefix.

The interface makes no network/model calls and computes no orders, fills,
commissions, slippage, dividends, returns, drawdown or performance. It does not
check exchange-calendar completeness. T06 strategy execution and T07 strategy
evaluation remain incomplete.

```sh
python -m unittest tests.test_backtest_data_contract tests.test_backtest_strategy_input -v
```
