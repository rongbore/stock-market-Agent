import unittest

from scripts.ai_review_budget_preflight import (
    MONTHLY_CAP_FEN,
    evaluate_budget_preflight,
)


def ledger(**overrides):
    value = {
        "period": "2026-11",
        "spent_fen": 200,
        "reserved_fen": 100,
        "revision": 7,
        "limit_fen": MONTHLY_CAP_FEN,
    }
    value.update(overrides)
    return value


class BudgetPreflightTests(unittest.TestCase):
    def test_exact_cap_is_within_cap_but_never_authorizes_call(self):
        result = evaluate_budget_preflight(
            ledger=ledger(spent_fen=200, reserved_fen=100),
            current_period="2026-11",
            requested_reservation_fen=200,
        )
        self.assertEqual(result["status"], "WITHIN_CAP")
        self.assertFalse(result["model_call_authorized"])
        self.assertFalse(result["reservation_committed"])
        self.assertEqual(result["remaining_fen"], 200)

    def test_reservation_over_cap_blocks(self):
        result = evaluate_budget_preflight(
            ledger=ledger(), current_period="2026-11", requested_reservation_fen=201
        )
        self.assertIn("insufficient_budget", result["reasons"])

    def test_stale_period_blocks_without_reset(self):
        result = evaluate_budget_preflight(
            ledger=ledger(period="2026-10"), current_period="2026-11",
            requested_reservation_fen=1,
        )
        self.assertIn("stale_ledger_period", result["reasons"])

    def test_missing_or_extra_ledger_fields_block(self):
        for value in (None, {}, ledger(extra="unexpected")):
            with self.subTest(value=value):
                result = evaluate_budget_preflight(
                    ledger=value, current_period="2026-11", requested_reservation_fen=1
                )
                self.assertEqual(result["status"], "BLOCKED")

    def test_boolean_is_not_accepted_as_integer(self):
        result = evaluate_budget_preflight(
            ledger=ledger(spent_fen=True), current_period="2026-11",
            requested_reservation_fen=True,
        )
        self.assertIn("invalid_spent_fen", result["reasons"])
        self.assertIn("invalid_requested_reservation", result["reasons"])

    def test_cap_cannot_be_raised_in_ledger(self):
        result = evaluate_budget_preflight(
            ledger=ledger(limit_fen=50000), current_period="2026-11",
            requested_reservation_fen=1,
        )
        self.assertIn("fixed_cap_mismatch", result["reasons"])

    def test_invalid_periods_block(self):
        result = evaluate_budget_preflight(
            ledger=ledger(period="2026-13"), current_period="2026-13",
            requested_reservation_fen=1,
        )
        self.assertIn("invalid_current_period", result["reasons"])
        self.assertIn("invalid_ledger_period", result["reasons"])

    def test_overspent_ledger_blocks(self):
        result = evaluate_budget_preflight(
            ledger=ledger(spent_fen=501, reserved_fen=0), current_period="2026-11",
            requested_reservation_fen=1,
        )
        self.assertIn("ledger_over_cap", result["reasons"])


if __name__ == "__main__":
    unittest.main()
