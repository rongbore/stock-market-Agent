# Human-readable financial table review report

```sh
python -m scripts.financial_table_review_report --package review.json --output review.md
python -m scripts.financial_table_review_report --package review.json --annotations annotations.json --max-rows 100 --output review.md
```

The Markdown report shows original candidate numeric text, cell positions,
metric/unit/period hints, original blockers and caller-supplied review decisions.
Both PDF and complete package SHA-256 are included. Annotation fingerprints must
match before any decision is displayed. The original JSON retains full cell
rectangles, header geometry and label fragments.

Display defaults to 100 rows, configurable from 1–500. Full candidate and pending
counts include omitted rows, and omission is explicit. Untrusted HTML/Markdown is
escaped and displayed fields are bounded. Output cannot overwrite input files and
is replaced atomically after validation. No network or model calls are made.

This is a review aid. Reviewer identity, financial values, provenance, publication
time and consolidation scope are not authenticated; accepted decisions do not
remove blockers or authorize release, merging or investment actions.
