# Merge readiness (read-only prototype)

`scripts/pr_merge_readiness.py` is a pure assessment helper. It has **no**
GitHub write token and **no** merge operation. A candidate requires:

- a non-draft open PR targeting `main` with confirmed mergeability;
- a valid immutable head SHA;
- a complete, small, documentation-only changed-file listing;
- successful `unit-tests` and `merge-policy` checks tied to that exact SHA;
- independently verified effective branch protection.

The `protected=True` parameter is **not evidence of protection**: only a
trusted controller can supply it after checking effective GitHub rules and
permissions. An attacker must not be able to set it using PR text, labels,
comments, or changed files. Check-run provenance, required-check configuration,
and head SHA must be revalidated at merge time. A future implementation must
also check all configured required checks and reviews, not only this prototype's
two named jobs. Never use this helper alone to authorize a merge.

Until those safeguards are implemented and reviewed, automatic merging
remains disabled.
