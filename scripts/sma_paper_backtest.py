"""Bounded offline long-only SMA paper simulation with next-observed-open fills."""
from decimal import Decimal, localcontext
import math

from scripts.backtest_data_contract import _day, build_backtest_dataset
from scripts.backtest_strategy_input import sma_schedule

MAX_BARS = 2000
MAX_SHARES = 10 ** 12


def _amount(value, name, minimum, maximum):
    if type(value) not in (int, float):
        raise ValueError(f"{name} must be a finite number")
    try:
        valid = math.isfinite(value) and minimum <= value <= maximum
    except OverflowError:
        valid = False
    if not valid:
        raise ValueError(f"{name} outside supported range")
    return Decimal(str(value))


def run_sma_paper_backtest(snapshot, *, evidence_as_of, expected_adjustment, window,
                           initial_cash, board_lot_size, commission_bps, minimum_fee,
                           sell_tax_bps, slippage_bps, execution_start_date=None):
    """Run causal SMA targets through the shared paper-execution accounting."""
    return _run_paper_backtest(
        snapshot, evidence_as_of=evidence_as_of, expected_adjustment=expected_adjustment,
        window=window, initial_cash=initial_cash, board_lot_size=board_lot_size,
        commission_bps=commission_bps, minimum_fee=minimum_fee, sell_tax_bps=sell_tax_bps,
        slippage_bps=slippage_bps, execution_start_date=execution_start_date, mode="sma")


def run_buy_and_hold_paper_backtest(snapshot, *, evidence_as_of, expected_adjustment,
                                    initial_cash, board_lot_size, commission_bps,
                                    minimum_fee, sell_tax_bps, slippage_bps):
    """Attempt one predeclared purchase at first observed open; never force a sale."""
    return _run_paper_backtest(
        snapshot, evidence_as_of=evidence_as_of, expected_adjustment=expected_adjustment,
        window=1, initial_cash=initial_cash, board_lot_size=board_lot_size,
        commission_bps=commission_bps, minimum_fee=minimum_fee, sell_tax_bps=sell_tax_bps,
        slippage_bps=slippage_bps, execution_start_date=None, mode="buy_and_hold")


def _run_paper_backtest(snapshot, *, evidence_as_of, expected_adjustment, window,
                        initial_cash, board_lot_size, commission_bps, minimum_fee,
                        sell_tax_bps, slippage_bps, execution_start_date, mode):
    """Simulate one unadjusted symbol without borrowing or forced liquidation.

    Settings are mandatory assumptions, not inferred exchange or broker rules.
    Each completed-bar target can execute only at the next observed bar open.
    """
    if expected_adjustment != "unadjusted":
        raise ValueError("paper simulation supports unadjusted bars only")
    if type(window) is not int or not 1 <= window <= MAX_BARS:
        raise ValueError("window must be 1 to 2000")
    if type(board_lot_size) is not int or not 1 <= board_lot_size <= 1000000:
        raise ValueError("invalid board lot size")
    cash0 = _amount(initial_cash, "initial_cash", 0.01, 10 ** 15)
    rate = _amount(commission_bps, "commission_bps", 0, 1000) / 10000
    fee_floor = _amount(minimum_fee, "minimum_fee", 0, 10 ** 9)
    tax_rate = _amount(sell_tax_bps, "sell_tax_bps", 0, 1000) / 10000
    slip = _amount(slippage_bps, "slippage_bps", 0, 1000) / 10000
    dataset = build_backtest_dataset(snapshot, evidence_as_of=evidence_as_of,
                                     expected_adjustment=expected_adjustment)
    bars = dataset["bars"]
    if len(bars) > MAX_BARS:
        raise ValueError("paper simulation limited to 2000 bars")
    execution_start = None
    if execution_start_date is not None:
        execution_start = _day(execution_start_date).isoformat()
        if execution_start not in {bar["date"] for bar in bars}:
            raise ValueError("execution_start_date must identify an observed bar")
    prices = []
    for bar in bars:
        prices.append({key: _amount(bar[key], key, 0.000001, 10 ** 9)
                       for key in ("open", "high", "low", "close")})
    schedule = sma_schedule(bars, window) if mode == "sma" else [
        {"signal_date": None, "target_weight": 1} for _ in bars]
    with localcontext() as context:
        context.prec = 40
        cash, shares = cash0, 0
        fills, marks, skipped = [], [], []
        total_commission = total_tax = total_slippage = Decimal(0)
        for index, (bar, price) in enumerate(zip(bars, prices)):
            # Earlier bars are signal warmup only: no fills, fees or equity marks.
            if execution_start is not None and bar["date"] < execution_start:
                continue
            if mode == "sma":
                pending = schedule[index - 1] if index else None
            else:
                # Fixed benchmark decision is declared before the first open.
                # If that one attempt is skipped there is no later retry.
                pending = schedule[0] if index == 0 else None
            target = pending["target_weight"] if pending else None
            side = "buy" if target == 1 and shares == 0 else "sell" if target == 0 and shares > 0 else None
            if side and bar["volume"] == 0:
                skipped.append({"signal_date": pending["signal_date"], "date": bar["date"],
                                "reason": "zero_reported_volume"})
                side = None
            if side:
                execution_price = price["open"] * (1 + slip if side == "buy" else 1 - slip)
                if side == "buy":
                    # Binary-search affordable lots including minimum commission.
                    lo, hi = 0, min(int(cash / (execution_price * board_lot_size)),
                                    MAX_SHARES // board_lot_size)
                    while lo < hi:
                        middle = (lo + hi + 1) // 2
                        notional = execution_price * (middle * board_lot_size)
                        if notional + max(notional * rate, fee_floor) <= cash:
                            lo = middle
                        else:
                            hi = middle - 1
                    quantity = lo * board_lot_size
                else:
                    quantity = shares
                notional = execution_price * quantity
                commission = max(notional * rate, fee_floor) if quantity else Decimal(0)
                tax = notional * tax_rate if side == "sell" else Decimal(0)
                after = cash - notional - commission if side == "buy" else cash + notional - commission - tax
                if not quantity or after < 0:
                    skipped.append({"signal_date": pending["signal_date"], "date": bar["date"],
                                    "reason": "no_affordable_lot" if not quantity else "unaffordable_sell_fees"})
                else:
                    cash = after
                    shares += quantity if side == "buy" else -quantity
                    slippage_cost = abs(execution_price - price["open"]) * quantity
                    total_commission += commission
                    total_tax += tax
                    total_slippage += slippage_cost
                    fills.append({"signal_date": pending["signal_date"], "date": bar["date"],
                                  "side": side, "quantity": quantity,
                                  "observed_open": float(price["open"]),
                                  "execution_price": float(execution_price), "notional": float(notional),
                                  "commission": float(commission), "sell_tax": float(tax),
                                  "slippage_cost": float(slippage_cost), "cash_after": float(cash),
                                  "shares_after": shares})
            equity = cash + shares * price["close"]
            if not equity.is_finite() or equity < 0 or cash < 0 or shares < 0:
                raise ValueError("invalid accounting state")
            marks.append({"date": bar["date"], "close": float(price["close"]),
                          "cash": float(cash), "shares": shares,
                          "equity": float(equity), "target_weight": schedule[index]["target_weight"]})
        final_equity = cash + shares * prices[-1]["close"]
        return {
            "schema_version": "0.1", "symbol": dataset["symbol"],
            "status": "EXPERIMENTAL_PAPER_BACKTEST_UNVERIFIED",
            "assumptions": {"strategy": mode, "window": window if mode == "sma" else None,
                            "initial_cash": float(cash0),
                            "board_lot_size": board_lot_size, "commission_bps": commission_bps,
                            "minimum_fee": minimum_fee, "sell_tax_bps": sell_tax_bps,
                            "slippage_bps": slippage_bps,
                            "execution": "next_observed_bar_open" if mode == "sma" else "first_observed_bar_open_predeclared",
                            "adjustment": "unadjusted", "forced_liquidation": False,
                            "execution_start_date": execution_start,
                            "money_rounding": "decimal_calculation_without_currency_quantization"},
            "evidence_as_of": dataset["evidence_as_of"], "signals": schedule,
            "fills": fills, "skipped": skipped, "marks": marks,
            "initial_cash": float(cash0), "final_cash": float(cash), "final_shares": shares,
            "final_marked_equity": float(final_equity),
            "experimental_total_return": float(final_equity / cash0 - 1),
            "total_commission": float(total_commission), "total_sell_tax": float(total_tax),
            "total_slippage_cost": float(total_slippage),
            "last_signal_has_no_next_bar": mode == "sma" and schedule[-1]["target_weight"] is not None,
            "source_content_verified": False, "historical_point_in_time_verified": False,
            "exchange_calendar_checked": False,
            "limitations": ["No proof of historical data availability or source authenticity.",
                            "No price-limit, suspension, liquidity, partial-fill or auction modeling.",
                            "No corporate actions, dividends or odd-lot handling.",
                            "Next observed bar may follow missing sessions; no calendar completeness check.",
                            "Final holdings are marked at the final close, not liquidated.",
                            "Experimental return is not a profitability claim or recommendation."],
        }
