# v0.2 release evidence gate (Issue #35)

This checklist is a **manual, fail-closed release review**, not a declaration that v0.2 is released. Do not auto-merge `main`, enable trading, upload secrets, or spend money on AI models to complete this checklist.

## 1. Pin the exact candidate

- [ ] Record the full `main` commit SHA and the review timestamp in Beijing time.
- [ ] Re-query open PRs and inspect each PR's base/head SHA, draft state, changed files, reviews and CI. An empty PR list does not prove every past PR was reviewed.
- [ ] Identify the exact CI runs for that SHA; never substitute an older green run or a PR author's unverified test claim.

## 2. Required test evidence

- [ ] Python input tests: completed/success for the candidate SHA.
- [ ] Offline report artifact E2E: completed/success for the candidate SHA.
- [ ] Security scan: independently identify a configured scanner and its completed/success run for the candidate SHA. If absent, mark **BLOCKED**, not green.
- [ ] Verify tests actually executed rather than being skipped because optional dependencies were missing.
- [ ] Record URLs, run IDs, timestamps and tested SHAs in the release review record.

## 3. Real-data provenance: one A-share instrument minimum

- [ ] Record ticker with exchange suffix, instrument identity, period, price units, adjustment convention, and timezone.
- [ ] Preserve the original upstream response or official announcement/PDF bytes; record SHA-256 of **raw bytes** separately from any normalized-data hash.
- [ ] Record the authoritative source URL, collection timestamp, publication/disclosure timestamp, and the requested historical as-of cutoff.
- [ ] Prove the source was available no later than the as-of cutoff; missing or ambiguous publication time is **UNVERIFIED**.
- [ ] Reconcile reported values, financial statement period and units against the captured evidence. Disagreements must remain visible.
- [ ] Confirm the Chinese report cites the exact source artifact and clearly labels missing, single-source, conflicting, synthetic and unverified data.
- [ ] Keep any real source acquisition opt-in and read-only. No broker connection or trading endpoint is permitted.

## 4. Branch and review protection

- [ ] Check `GET /repos/{owner}/{repo}/branches/main` and the applicable repository rulesets.
- [ ] Verify effective rules include mandatory PR review, required CI checks, and restrictions on direct pushes/bypass; an `active` ruleset with `rules: []` is **not** effective protection.
- [ ] Re-check effective protection after any administrator change. This checklist does not itself change security settings.
- [ ] Never infer merge authorization from a green workflow or an AI-generated recommendation.

## 5. Paid-model budget (Asia/Shanghai calendar month)

- [ ] Independently verify all paid-model charges already incurred this month, including other scheduled runs.
- [ ] Establish a hard maximum cost for the proposed call, including retries and output tokens, **before** execution.
- [ ] If either number cannot be verified, make **zero** paid calls and use free/offline tests instead.
- [ ] Refuse a call if verified month-to-date spend plus worst-case next-call cost exceeds **CNY 5**.
- [ ] Log timestamp, provider/model, purpose, request ID, verified charge, month-to-date cumulative charge and remaining budget; avoid repeat scheduled validation.

## Release decision

**BLOCKED** if any required evidence is absent, failed, stale, skipped or ambiguous. Record the specific blocker and owner; do not mark Issue #35 complete or label the release production-ready. P1 items may be deferred with an explicit risk note, but P0 evidence, safety and provenance requirements may not be waived.

Suggested review record fields: `candidate_sha`, `reviewed_at_bjt`, `ci_run_urls`, `security_scan_url`, `source_artifact_sha256`, `source_url`, `disclosed_at`, `as_of`, `provenance_status`, `branch_protection_status`, `paid_month_cny_verified`, `decision`, `blockers`.
