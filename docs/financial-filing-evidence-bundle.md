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
Currency units use exact labels and values are decimal strings. Only canonical
HTTPS CNINFO finalpage PDFs are accepted. Requested pages are parsed, and each
manual excerpt must appear in the corresponding page text and contain the
declared metric label and value. The page must also contain the matching report
period heading: `本报告期`, `年初至报告期末`, or `本报告期末`.

This contract does not fetch or authenticate a filing, inspect PDF table cells,
verify the relationship between a header and a table column, or infer missing units.
The excerpt must name exactly one matching currency unit (`元`, `万元`, or `亿元`).
Numeric matching rejects partial numbers and ambiguous adjacent signs. Flattened
PDF rows can therefore require better cell evidence before acceptance, including
the example cash-flow row whose placeholder dashes touch its negative amount.
These checks do not verify manually entered numbers.

Page text and excerpts remain untrusted;
matching text does not prove the value belongs to the intended table column.
Every bundle remains
`PENDING_MANUAL_VERIFICATION`; supplied timestamps do not establish the
provider's historical publication time. It makes no model, brokerage, or paid
API calls.

Run the focused tests with:

```sh
python -m unittest tests.test_financial_filing_evidence_bundle -v
```

## Reproducing the 000776.SZ sample

`examples/financial_evidence/000776.SZ_2026Q3_input.json` records the CNINFO
2026 Q3 report URL, observed SHA-256, disclosure timestamp listed by CNINFO,
retrieval timestamp, and five page-1 metric excerpts. The PDF itself is not
included; obtain it from the official URL in the record, then run:

```sh
python -m scripts.financial_filing_evidence_bundle \
  --input examples/financial_evidence/000776.SZ_2026Q3_input.json \
  --pdf /path/to/1225643508.PDF \
  --output results/000776.SZ_2026Q3_evidence_bundle.json
```

The run checks the downloaded bytes against the recorded digest and parses the
cited pages. It still does not independently prove the filing's origin or
timestamp, or verify that each number belongs to the intended financial
statement row and column. Human review remains required.
