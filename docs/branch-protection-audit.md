# Main protection audit: read-only groundwork

The GitHub repository Rulesets endpoint currently returns an empty list.
The legacy `branches/main/protection` endpoint returned HTTP 403 to the
available integration. This is **unknown**, not proof of protection.

`scripts/branch_protection_audit.py` intentionally returns **not verified**
for these inputs, and even for apparently sufficient summary metadata. It
cannot grant merge permission. No GitHub write token or auto-merge workflow
is included.

Before any privileged merger can be enabled, an administrator must verify:

1. Effective `main` protection against direct pushes, deletion and force push.
2. Required checks with correct GitHub App provenance and fresh SHA; avoid
   requiring path-filtered jobs that can remain pending.
3. Review requirements for sensitive changes, with no bypass for automation.
4. No workflow or bot token can edit the protection policy or bypass it.
5. The actual GitHub plan and ruleset enforcement, including repository and
   organization rules, not just ruleset names or API summaries.
6. A trusted merge-time recheck of PR head SHA, files, checks and protections.

**Do not enable automatic merging until an administrator completes this audit.**
