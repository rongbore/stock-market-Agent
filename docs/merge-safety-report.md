# Offline merge-safety diagnostic

The report tool is read-only and deliberately **cannot approve or merge** PRs.
It prints explicit blockers so maintainers can see why automatic merging is
not yet safe. It never connects to GitHub, requests credentials, or changes
repository settings.

Run from the repository root:

```bash
python -m scripts.merge_safety_report < audit-input.json
python -m unittest discover -s tests -p 'test_merge_safety_report.py' -v
```

Input is a JSON object with optional `rulesets`, `legacy_protection`,
`pr`, `files`, and `checks` keys. Missing or malformed data is blocked.
The current protection auditor does not certify effective protection, so
`ready` is always false. This is intentional: do not interpret a diagnostic
as authorization to enable a privileged merger.

Administrators must independently validate effective branch protection,
required CI provenance, bypass permissions and merge-time SHA checks before
a separate trusted executor is designed and enabled.
