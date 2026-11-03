# v0.2 cross-module integration checks

This draft branch stages copies of three independent PR modules to run
cross-module contract tests in GitHub CI:

- PR #3: run-level provenance metadata
- PR #5: source record format/time cutoff
- PR #7: A-share disclosure normalization

**Important:** These modules are copied into an isolated test branch.
They are not yet connected to the live TradingAgents execution path.
Date-only A-share disclosures must NOT be treated as verified historical
evidence. Format-valid timestamps are not proof of authentic publication.

The test uses synthetic inputs and requires no API keys or broker access.
This PR should not be merged as a replacement for its dependency PRs;
review the dependencies first, then carry the tests into the eventual
integration branch. No automatic merge is authorized.
