# Research report provenance (v0.2 groundwork)

Each completed analysis writes `run_provenance.json` alongside the HTML report.
It records ticker, requested analysis date, generation time (UTC), model ID,
and optional GitHub Actions run ID. It intentionally contains no API key or
private portfolio information.

**Important:** This is *run-level metadata*, not independently validated
market-data provenance. `market_data_sources_verified` remains `false`
and `source_records` is empty until upstream data-provider URLs, as-of dates,
publication timestamps, and data hashes can be captured and checked.

Do not interpret the requested analysis date as proof of point-in-time data
integrity. Next steps: source adapters, publication-time checks, and citations
in the generated report. This feature does not connect to a brokerage.
