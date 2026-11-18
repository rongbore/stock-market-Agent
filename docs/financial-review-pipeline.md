# One-command offline financial review materials

```sh
python -m scripts.financial_review_pipeline --pdf /path/to/filing.pdf --symbol 000776.SZ --announcement-date 2026-10-30 --pages 1 --output /path/to/review-artifact.json
```

The command runs local table extraction, hint generation, structural acceptance,
annotation binding and Markdown rendering. One atomically replaced JSON artifact
contains `package`, `validation`, `review_record` and `report_markdown`, avoiding
partial sidecar files. Install optional `pdfplumber` to parse PDFs. No network or
model calls occur.

To record decisions, use the emitted PDF hash and `validation.package_sha256`
in an annotation JSON matching the review-annotations contract, then rerun with
`--annotations /path/to/annotations.json`. Stale annotations fail before output
replacement. Regeneration with changed parser behavior or coordinates can change
the package hash and require a fresh review. `--max-rows` controls display only;
the artifact retains every candidate and all counts.

`REVIEW_MATERIALS_READY_UNVERIFIED` means numeric review materials exist, not that
financial data is verified or that release is authorized. An empty numeric table
produces `NO_NUMERIC_EVIDENCE` with its blocker preserved. Every candidate still
requires consolidation-scope and manual financial verification. A final PDF hash
check catches changes during artifact construction but does not authenticate the
publisher or establish a verified historical publication time. Reviewer labels
are caller assertions; even accepted decisions never remove verification blockers.

Run `python -m unittest tests.test_financial_review_pipeline -v` for real-parser
end-to-end checks using clearly synthetic Chinese PDF tables. These checks do not
constitute actual issuer-report accuracy acceptance.

## Explicit annual header hints

The artifact additionally contains `annual_header_hints_unverified`, separate from
the strict review package and its existing annotation hash. Exact `19xx年` /
`20xx年` and `年末` labels may provide an integer year and an `annual` / `year_end`
basis hint. Explicit `调整前` / `调整后` child rectangles provide a restatement hint
only when the entire numeric rectangle belongs to exactly one header chain.
Absent sublabels mean unknown restatement basis. The latest year block is used;
unknown intervening text in the numeric column is a barrier. No cross-page or
cross-table matching or center-only fallback is used. Quarterly labels remain
unsupported by this annual hint module.

Hint candidates retain number/header cell coordinates. These are unverified
geometry hints, not normalized financial periods or accepted claims. They do not
clear existing `period`, consolidation-scope or manual-review blockers and do not
alter reviewer annotations. The Markdown report still presents the existing
strict package; inspect the extra JSON section for annual hints.

The pipeline performs an additional bounded table extraction and verifies its PDF
hash against the original package and a final file digest. This adds parser work;
changes to the PDF fail the whole artifact. No network or model call is added.

When restatement labels occupy narrower rectangles than values, an additional
explicit row-partition rule can produce hints: exactly two numeric rectangles
must tile the entire parent year width with no gap or overlap (coordinate equality
tolerance 1e-6 PDF points), share row top/bottom, and each fully contain exactly
one of a unique same-row before/after label pair. No midpoint, nearest-center or
width extrapolation is used. The two number rectangles are retained in
`partition_cells_unverified`, with reason
`explicit_restatement_row_partition_unverified`. Missing halves, ambiguous labels
or three-column layouts do not use this rule. This still supplies hints only and
does not clear any financial-review blocker.
