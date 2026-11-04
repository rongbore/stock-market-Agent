# GitHub main protection setup (manual administrator checklist)

**Status:** automatic merging is disabled. This document is an administrator
checklist, not an automated change to repository settings.

1. Open repository **Settings → Rules → Rulesets** (or Branches → branch
   protection, depending on available GitHub plan and permissions).
2. Create an active rule targeting exactly the default branch `main`.
   Disallow branch deletion and force pushes; require pull requests rather
   than direct pushes. Inspect any organization-level rules too.
3. Require the always-running checks **unit-tests** and **merge-policy**,
   selecting the correct GitHub Actions source when available. Do not make
   path-filtered jobs mandatory for unrelated PRs.
4. Configure approvals for sensitive changes, review dismissal on new pushes,
   and any required conversation resolution. Check whether the repository's
   contributor/reviewer structure can actually satisfy the policy.
5. Inspect all bypass actors and administrator enforcement. The future
   automation identity must not be able to bypass required checks, reviews,
   or modify the protection policy.
6. Test with a harmless PR: verify that failing CI blocks merging, an
   unreviewed sensitive PR cannot merge, and direct pushes are rejected.
7. Re-query **effective** protection and record its scope, enforcement,
   required checks, reviews and bypass configuration for independent review.

The current GitHub integration observed an empty repository Rulesets list and
cannot read the legacy branch protection endpoint (HTTP 403). Neither
observation proves that all effective rules are absent, but neither establishes
the protections needed to enable a privileged merger.

For an offline diagnostic, create an audit-input JSON object from trusted
API responses, then run:

```bash
python -m scripts.merge_safety_report --strict audit-input.json
```

Exit code `2` means merge readiness is **not verified**; code `0` is
reserved for a future fully verified implementation. The report currently
always returns `ready: false`. Never turn off strict mode to justify merging.
