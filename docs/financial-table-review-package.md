# Offline table review package

Run from the repository root with optional `pdfplumber` installed:

```sh
python -m scripts.financial_table_review_package --pdf /path/to/filing.pdf --symbol 000776.SZ --announcement-date 2026-10-30 --pages 1 --output /path/to/review.json
```

The package binds extracted cell and header rectangles and label fragments to
the local PDF SHA-256. Candidates retain their original numeric text and expose
unverified metric, currency-unit and reporting-period hints. `review_blockers`
lists missing hints; consolidation scope and manual verification always remain
required. No candidate is accepted as a verified financial claim. The supplied
announcement date does not establish publication time or historical availability.

The package includes `candidate_count` and top-level `review_blockers`. An empty
extraction adds `no_numeric_candidates`; an empty result is not successful financial
evidence acceptance. All packages retain consolidation-scope and manual-review blockers.

Run the real-parser synthetic-table integration checks with:

```sh
python -m unittest tests.test_financial_table_review_integration -v
```

These tests construct a Chinese-labelled PDF table, extract it with real
`pdfplumber`, and run the review CLI without mocking extraction. They cover
negative numbers beside placeholders, period/metric/unit hints and empty numeric
evidence. They explicitly skip when the optional parser is absent. Synthetic
integration success does not establish real issuer filing accuracy.

Only requested pages are inspected. Unsupported layouts and units can leave
hints missing. Review against the original PDF, including report year, column
meaning, unit and consolidated versus parent-company scope. This command makes
no network or model calls. Output is replaced atomically after successful
extraction and validation; the source PDF cannot be the output target.
