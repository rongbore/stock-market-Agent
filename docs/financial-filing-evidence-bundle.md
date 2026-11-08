# Financial filing evidence bundle

`scripts/financial_filing_evidence_bundle.py` joins a local filing PDF with a
source record and manually transcribed metric claims. It checks the actual
file's SHA-256, timezone-aware publication/retrieval timestamps, the analysis
cutoff, symbol consistency, page number, normalized metric label, unit,
consolidation scope, and whether the period is a quarter, year-to-date, or
period-end value.

For quarterly reports, `period_basis` must be explicit. A `year_to_date` claim
must begin on January 1; a `current_quarter` claim must begin at the calendar
quarter boundary; `period_end` is reserved for point-in-time total assets.
Currency units use exact labels and values are decimal strings.

This contract does not fetch or authenticate a filing, inspect PDF table cells,
or verify manually entered numbers. Every bundle remains
`PENDING_MANUAL_VERIFICATION`; supplied timestamps do not establish the
provider's historical publication time. It makes no model, brokerage, or paid
API calls.

Run the focused tests with:

```sh
python -m unittest tests.test_financial_filing_evidence_bundle -v
```
