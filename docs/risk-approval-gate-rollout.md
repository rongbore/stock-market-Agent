# Risk-based approval gate: safe rollout

The current active `main-protection-default-auto-merge` ruleset requires
`unit-tests` and `merge-policy` but **zero approvals**. This does not
enforce manual review for sensitive changes.

`scripts/risk_approval_gate.py` is a pure, fail-closed policy helper:
- Only a complete, small, docs-only PR can pass without review.
- All other changes require an independent APPROVED review after the latest
  head commit's push time, and the reviewer's latest state must still approve.
- Missing metadata blocks the gate.

**Not yet an enforcement mechanism.** Before changing the ruleset or
enabling an automatic merger, implement a trusted `pull_request_target`
workflow running policy code exclusively from protected `main` without
checking out PR content, fetch all paginated files and reviews, verify the
latest head SHA and review provenance, and make its dedicated check required
in the active ruleset. A failed/absent gate must block merging. Validate with
an unapproved sensitive PR and a low-risk docs PR.

The ruleset must also prevent bypass of the gate and ensure changes to
workflow/policy files are reviewed. Never use a PR-controlled workflow's
green status as authorization to merge.
