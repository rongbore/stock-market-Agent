# Low-risk PR auto-merge rollout (not yet enabled)

This repository intentionally does **not** automatically merge pull requests.

## Phase 1: classification only

The read-only `merge-policy` job classifies candidate PRs; its PR code is
untrusted, so its output is informational only. It identifies
small, documentation-only candidates. Any source, tests, workflow, secret,
market-data, financial, report, or unrecognized change is **manual review**.
A classification of `eligible` is informational and **not approval to merge**.

## Phase 2: required GitHub protections

Before enabling an auto-merge bot, an administrator must protect `main`
against direct pushes, force pushes and deletion; require the actual
`unit-tests` and `merge-policy` check names; and verify that workflow
permissions and bypass lists cannot circumvent these protections. Check
GitHub plan and ruleset availability. Do not require path-filtered checks
for PRs where those jobs are skipped.

## Phase 3: separate privileged merger

A future privileged workflow must run only trusted code from `main`, never
checkout or execute PR head code with write credentials. It must verify the
current PR head SHA, draft status, changed files (including renames/deletions),
CI success, mergeability, and protection state immediately before requesting
auto-merge. Unknown, large, mixed, or sensitive changes require manual review.
Do not use a user-controlled label as proof of eligibility. Never grant a
privileged workflow permission to modify its own eligibility policy.

Do not enable automatic merging until a dedicated adversarial test and
administrator review confirm all conditions above.
