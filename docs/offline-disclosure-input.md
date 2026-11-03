# Optional offline A-share disclosure metadata

The analysis entrypoint supports an optional **local** JSON file supplied via
`ANALYSIS_DISCLOSURES_JSON`. The file must contain an array of disclosure
metadata objects with `symbol`, `title`, `provider`, `url`, and
`announcement_date` (YYYY-MM-DD). The source is **not** fetched or authenticated.

Example synthetic input (not a real announcement):

```json
[
  {
    "symbol": "000776.SZ",
    "title": "SYNTHETIC TEST NOTICE",
    "provider": "offline-test",
    "url": "https://example.org/synthetic",
    "announcement_date": "2026-01-01"
  }
]
```

When the variable is set, `scripts/analyze.py` saves
`disclosure_candidates.json` alongside the HTML report and provenance files.
Strict artifact validation checks the candidate file against the analysis date
and ticker. It does **not** mark the candidates as verified evidence, include
them in `evidence_bundle.json`, or assert that TradingAgents used them.

The GitHub Actions analysis workflow does not currently pass this environment
variable or accept a disclosure file upload. This interface is intended for
local or controlled future adapter use. The real analysis entrypoint still
requires its configured model API key; do not run it merely to test this
metadata feature. For a free offline test, use
`python -m scripts.disclosure_candidates input.json --analysis-date 2026-01-02 --symbol 000776.SZ --output-dir output`.
