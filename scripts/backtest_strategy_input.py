"""Causal bar-prefix strategy interface; signals only, not fills or PIT proof."""
import math
from types import MappingProxyType

from scripts.backtest_data_contract import _day, build_backtest_dataset


def sma_schedule(bars, window):
    """Build close-only targets from already validated bars, with warm-up gaps."""
    if type(window) is not int or not 1 <= window <= 100000:
        raise ValueError("window must be an integer from 1 to 100000")
    result = []
    for index, bar in enumerate(bars):
        target = None
        if index + 1 >= window:
            average = math.fsum(row["close"] / window for row in bars[index + 1 - window:index + 1])
            target = 1 if bar["close"] > average else 0
        result.append({"signal_date": bar["date"], "target_weight": target})
    return result


def run_strategy_signal(snapshot, *, evidence_as_of, expected_adjustment,
                        signal_date, min_history, strategy):
    """Validate a snapshot, then expose only completed bars through signal_date.

    The callable receives read-only copies of the historical prefix, never later
    bars, the total dataset length or the requested dataset end date. It returns
    a finite long-only target weight in [0, 1]. No execution date is inferred.
    """
    if type(min_history) is not int or not 1 <= min_history <= 100000:
        raise ValueError("min_history must be an integer from 1 to 100000")
    if not callable(strategy):
        raise ValueError("strategy must be callable")
    day = _day(signal_date)
    dataset = build_backtest_dataset(snapshot, evidence_as_of=evidence_as_of,
                                     expected_adjustment=expected_adjustment)
    prefix = [bar for bar in dataset["bars"] if bar["date"] <= day.isoformat()]
    if not prefix or prefix[-1]["date"] != day.isoformat():
        raise ValueError("signal_date must identify an observed daily bar")
    if len(prefix) < min_history:
        raise ValueError("insufficient historical bars")
    context = MappingProxyType({
        "symbol": dataset["symbol"], "signal_date": day.isoformat(),
        "bars": tuple(MappingProxyType(dict(bar)) for bar in prefix),
        "price_unit": dataset["price_unit"], "volume_unit": dataset["volume_unit"],
        "adjustment": dataset["adjustment"],
        "source_content_verified": False, "historical_point_in_time_verified": False,
    })
    weight = strategy(context)
    if type(weight) not in (int, float):
        raise ValueError("strategy must return a finite target weight in [0, 1]")
    try:
        valid = math.isfinite(weight) and 0 <= weight <= 1
    except OverflowError:
        valid = False
    if not valid:
        raise ValueError("strategy must return a finite target weight in [0, 1]")
    return {
        "schema_version": "0.1", "symbol": dataset["symbol"],
        "signal_date": day.isoformat(), "history_count": len(prefix),
        "target_weight": float(weight), "adjustment": dataset["adjustment"],
        "price_unit": dataset["price_unit"], "volume_unit": dataset["volume_unit"],
        "evidence_as_of": dataset["evidence_as_of"],
        "source_content_verified": False, "historical_point_in_time_verified": False,
        "exchange_calendar_checked": False, "status": "EXPERIMENTAL_SIGNAL_ONLY",
        "execution_policy": "UNSPECIFIED_NO_FILLS",
        "limitations": [
            "A historical bar prefix is not proof of historical data availability.",
            "Currently retrieved adjusted bars may contain later corporate actions.",
            "The callable is trusted caller code, not an execution sandbox.",
            "No execution time, order, fill, fees, returns or performance is computed.",
        ],
    }


def sma_signal(snapshot, *, evidence_as_of, expected_adjustment, signal_date, window):
    """Target 1 when signal close exceeds trailing SMA, otherwise 0 (ties: 0)."""
    if type(window) is not int or not 1 <= window <= 100000:
        raise ValueError("window must be an integer from 1 to 100000")

    def baseline(context):
        closes = [bar["close"] for bar in context["bars"][-window:]]
        average = math.fsum(close / window for close in closes)
        return 1 if closes[-1] > average else 0

    result = run_strategy_signal(
        snapshot, evidence_as_of=evidence_as_of, expected_adjustment=expected_adjustment,
        signal_date=signal_date, min_history=window, strategy=baseline)
    result.update(strategy="close_above_trailing_sma", window=window)
    return result
