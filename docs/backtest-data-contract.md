# Offline daily-bar contract (T06 foundation)

`scripts.backtest_data_contract.build_backtest_dataset` accepts the existing
AKShare daily snapshot shape from either the Eastmoney or Sina adapter. It
validates data and returns an in-memory dataset for future strategy interfaces.

```python
from scripts.backtest_data_contract import build_backtest_dataset

dataset = build_backtest_dataset(
    snapshot,
    evidence_as_of="2026-11-03T16:00:00+08:00",
    expected_adjustment="unadjusted",
)
```

The adjustment argument is mandatory: `unadjusted`, `forward_adjusted`, or
`backward_adjusted` must match the snapshot's explicit `adjust` field (`""`,
`qfq`, or `hfq`). Price units must be `CNY_per_share`. Eastmoney volume must be
declared in `lots_100_shares`; Sina volume must be declared in `shares`. Output
volume is normalized to shares without changing the input. No unit is inferred.

Bars must be nonempty, unique, strictly ascending, canonical ISO dates within
the requested snapshot range, with exactly date/open/high/low/close/volume
fields. Prices are finite positive numbers; volume is finite and nonnegative.
Boolean and string numeric values are rejected. High/low must contain open
and close. No sorting, missing-session filling, rounding or price conversion is
performed. Weekend bars are rejected, but exchange holidays, suspensions and
missing trading sessions are not checked.

`evidence_as_of` is an explicit timezone-aware evidence cutoff, not a strategy's
simulated historical decision time. The snapshot's timezone-aware retrieval
timestamp must not exceed it. Every daily bar's nominal Shanghai 15:00 close
must be at or before both retrieval and cutoff; same-day incomplete bars are
rejected. This is a structural timing rule, not proof that a vendor finalized a
bar at that instant. The supplied timestamps are not independently authenticated.

Output provenance preserves source, upstream, interface, retrieval time, requested
range and input volume unit. Source and historical point-in-time verification
remain false. In particular, a currently retrieved adjusted series may encode
corporate actions unknown on simulated historical dates. This contract cannot
make it safe for point-in-time backtesting. T06 remains incomplete until strategy
inputs, corporate-action handling, exchange calendars and execution/cost
assumptions are designed and independently validated. No strategy, simulation,
performance calculation, network/model call or brokerage action is implemented.

Run focused checks with:

```sh
python -m unittest tests.test_backtest_data_contract -v
```
