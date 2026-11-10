"""Nonannualized metrics for bounded hypothetical mark-to-close equity paths."""
from decimal import localcontext

from scripts.backtest_data_contract import _day
from scripts.sma_paper_backtest import MAX_BARS, _amount


def paper_risk_metrics(run):
    """Compute observed-period return and peak-to-trough loss including initial cash."""
    if not isinstance(run, dict):
        raise ValueError("paper run must be an object")
    initial = _amount(run.get("initial_cash"), "initial_cash", 0.01, 10 ** 15)
    marks = run.get("marks")
    if not isinstance(marks, list) or not 1 <= len(marks) <= MAX_BARS:
        raise ValueError("paper marks must be nonempty and bounded")
    peak, worst = initial, initial * 0
    peak_date = trough_date = drawdown_peak_date = previous = None
    with localcontext() as context:
        context.prec = 40
        for mark in marks:
            if not isinstance(mark, dict):
                raise ValueError("invalid paper equity mark")
            day = _day(mark.get("date")).isoformat()
            if previous is not None and day <= previous:
                raise ValueError("equity marks must have ascending unique dates")
            value = _amount(mark.get("equity"), "equity", 0, 1e30)
            if value > peak:
                peak, peak_date = value, day
            drawdown = (peak - value) / peak
            if drawdown > worst:
                worst, trough_date, drawdown_peak_date = drawdown, day, peak_date
            previous = day
        final = _amount(run.get("final_marked_equity"), "final_marked_equity", 0, 1e30)
        if final != value:
            raise ValueError("final marked equity differs from last daily mark")
        return {
            "observed_period_return": float(final / initial - 1),
            "max_drawdown_fraction": float(worst),
            "max_drawdown_peak_date": drawdown_peak_date,
            "max_drawdown_trough_date": trough_date,
            "initial_capital_included_as_peak": True,
            "start_date": marks[0]["date"], "end_date": marks[-1]["date"],
            "observed_mark_count": len(marks), "annualized": False,
            "basis": "hypothetical_initial_cash_and_observed_close_marks",
            "verified_performance": False,
        }
