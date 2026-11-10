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
