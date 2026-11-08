# AI review budget preflight

`scripts/ai_review_budget_preflight.py` is a read-only calculation for the
existing ¥5 (500 fen) monthly paid-model limit. It rejects malformed or stale
ledger data, does not reset a ledger at month rollover, and does not permit the
limit to be raised through the supplied ledger object.

`WITHIN_CAP` means only that the submitted numbers fit arithmetically. The
result always has `model_call_authorized: false` and
`reservation_committed: false`. This module does not authenticate, persist, or
atomically reserve ledger state. Concurrent workflows could otherwise observe
the same remaining balance. A trusted durable ledger with atomic reservation
and per-call maximum-cost enforcement is still required before paid AI review
can be enabled. The existing GitHub workflow therefore remains disabled.
