"""Read-only fail-closed budget check for optional AI review.

This module never reserves or spends money and never authorizes a model call.
The ledger must be persisted and atomically reserved by a separate trusted
service before this preflight can be used as part of an invocation workflow.
"""
import re


MONTHLY_CAP_FEN = 500  # Fixed policy: ¥5.00 per calendar month.
_PERIOD = re.compile(r"^\d{4}-(0[1-9]|1[0-2])$")
_FIELDS = {"period", "spent_fen", "reserved_fen", "revision", "limit_fen"}


def evaluate_budget_preflight(*, ledger, current_period, requested_reservation_fen):
    """Check whether a requested worst-case reservation fits the fixed cap.

    Result is informational only: callers must never interpret it as authority
    to call a paid model. Exact schema and integer checks prevent coercion and
    policy-cap overrides. No missing/stale ledger is initialized implicitly.
    """
    reasons = []
    if not isinstance(current_period, str) or not _PERIOD.fullmatch(current_period):
        reasons.append("invalid_current_period")
    if type(requested_reservation_fen) is not int or requested_reservation_fen <= 0:
        reasons.append("invalid_requested_reservation")
    if not isinstance(ledger, dict):
        reasons.append("ledger_missing_or_invalid")
    else:
        if set(ledger) != _FIELDS:
            reasons.append("ledger_schema_mismatch")
        period = ledger.get("period")
        if not isinstance(period, str) or not _PERIOD.fullmatch(period):
            reasons.append("invalid_ledger_period")
        elif isinstance(current_period, str) and _PERIOD.fullmatch(current_period) and period != current_period:
            reasons.append("stale_ledger_period")
        for key in ("spent_fen", "reserved_fen", "revision", "limit_fen"):
            value = ledger.get(key)
            if type(value) is not int or value < 0:
                reasons.append("invalid_" + key)
        if type(ledger.get("limit_fen")) is int and ledger["limit_fen"] != MONTHLY_CAP_FEN:
            reasons.append("fixed_cap_mismatch")

    spent = ledger.get("spent_fen") if isinstance(ledger, dict) else None
    reserved = ledger.get("reserved_fen") if isinstance(ledger, dict) else None
    remaining = None
    if type(spent) is int and spent >= 0 and type(reserved) is int and reserved >= 0:
        remaining = max(0, MONTHLY_CAP_FEN - spent - reserved)
        if spent + reserved > MONTHLY_CAP_FEN:
            reasons.append("ledger_over_cap")
    if not reasons and requested_reservation_fen > remaining:
        reasons.append("insufficient_budget")

    return {
        "status": "WITHIN_CAP" if not reasons else "BLOCKED",
        "reasons": reasons,
        "period": current_period if isinstance(current_period, str) else None,
        "cap_fen": MONTHLY_CAP_FEN,
        "remaining_fen": remaining,
        "requested_reservation_fen": requested_reservation_fen if type(requested_reservation_fen) is int else None,
        "model_call_authorized": False,
        "reservation_committed": False,
    }
