# Run the read-only protection diagnostic manually

Open **Actions → Merge protection diagnostic → Run workflow** on the
default `main` branch. This workflow runs only on `main`, reads repository
Ruleset summaries with a read-only GitHub token, and invokes the existing
offline safety report in strict mode.

The workflow prints blockers and treats the expected diagnostic exit code
`2` as an informational result. It **does not enable auto-merge**, change
repository settings, or certify effective protection. If the Ruleset API is
inaccessible, the input is recorded as unknown (`null`), not as protected.

Even if a Ruleset summary exists, a trusted administrator must still verify
effective enforcement, required checks, review requirements, bypass actors
and legacy/organization protections. A green diagnostic workflow means only
that the **diagnostic executed correctly**, not that automatic merging is safe.
