# Local read-only research dashboard (T10 prototype)

## Reproducible three-panel demo

Install the optional PDF parser, then run from the repository root:

```sh
python -m pip install 'pdfplumber>=0.11,<0.13'
python -m scripts.offline_research_dashboard --batch-config examples/batch_research/SYNTHETIC_offline_pipeline.json --evaluation-config examples/backtest/SYNTHETIC_sma_oos_config.json --financial-config examples/financial_review/SYNTHETIC_dashboard_config.json --output SYNTHETIC_dashboard.html
```

Open `SYNTHETIC_dashboard.html` in a local browser that permits local files. The
page has batch, paper-evaluation and financial-review panels. Batch input deliberately
demonstrates one successful brief and two missing/invalid inputs; the PDF contributes
three financial numeric candidates, all pending review. Configured expenses and
prices are invented demonstration assumptions, not actual market or broker data.

The committed `examples/financial_review/SYNTHETIC_table.pdf` is a generated Chinese
table with a visible `合成测试数据` label. It is not a downloaded issuer filing.
Its config declares `SYNTHETIC`, uses a path relative to that config and includes
no reviewer assertions. Tests compare the entire PDF to its deterministic generator
and run this three-panel CLI twice, checking byte-identical HTML without mocking.
Successful generation does not establish browser layout or real-data acceptance.

## Individual sections

Generate one self-contained HTML page from the two **SYNTHETIC** raw fixtures:

```sh
python -m scripts.offline_research_dashboard --batch-config examples/batch_research/SYNTHETIC_offline_pipeline.json --evaluation-config examples/backtest/SYNTHETIC_sma_oos_config.json --output /tmp/SYNTHETIC_research_dashboard.html
```

Open the generated file in a local browser that permits local files. This is an
offline artifact, not a hosted service; the command does not serve, publish or
deploy anything. No JavaScript, external fonts, CDN, network requests, forms,
remote images or active content are included. The supplied prices, dates,
metadata and results are invented test material, not actual research on the
ticker. The first implementation has automated HTML/data tests; a rendered
browser visual inspection was not completed in the current environment.

At least one of `--batch-config`, `--evaluation-config`, or `--financial-config`
is required. Any one alone creates its respective section; combinations create
a combined page. An explicitly supplied null config is an error and cannot
silently disappear when another valid section is supplied.
The arguments are **raw input configurations**, not previously computed result
artifacts. `build_pipeline` and `build_evaluation_artifact` revalidate and
recompute their results before rendering; the financial panel re-extracts the
PDF through `build_financial_review_artifact`. Supplied output metrics or
financial packages are never accepted
as trusted figures. Input schemas and limits remain those documented in
[batch pipeline](offline-batch-pipeline.md) and
[evaluation CLI](sma-evaluation-cli.md).

The Chinese page shows:

- Batch job/success/failure counts, each symbol's status, missing inputs and
  validation failures. Successful output remains marked unverified, with no
  stock ranking. Optional report `fixture_notice` text appears as a caller's
  input note, limited to 800 characters; it is not evidence or an instruction.
- Training, SMA test and buy-and-hold test equity, observed-period returns,
  maximum drawdown, commissions/taxes and simulated fill counts.
- An inline SVG comparison of test account and benchmark mark-to-close equity,
  including initial capital before the first observed mark. X positions are
  equally spaced observations, not a complete trading calendar. The chart
  does not interpolate real market sessions or show intraday risk.
- Fixed window, chronological boundary, explicit capital/lot/cost assumptions,
  input and recomputed-payload SHA-256 values, and clear synthetic/unverified
  labels per section. A version string is metadata, not authenticated provenance.
- Optional financial numeric candidates with original cell text, page/table/row/
  column, metric/unit/period hints, preserved blockers, unknown consolidation
  scope and caller-recorded review decisions. Candidate and pending counts cover
  all extracted candidates, including those omitted from the bounded table.

For a local PDF, create a separate JSON config with exactly these fields:

```json
{
  "schema_version": "0.1",
  "data_kind": "UNVERIFIED_LOCAL",
  "pdf_path": "filing.pdf",
  "symbol": "000776.SZ",
  "announcement_date": "2026-10-30",
  "pages": [1],
  "annotations": null
}
```

The date and symbol are caller declarations, not source certification. Replace
them with the intended local document metadata. `filing.pdf` must actually exist;
the dashboard does not download it. In the CLI, relative PDF paths are resolved
against the **financial config file's directory**, not the shell working
directory. The Python API `build_dashboard(financial_config=...)` uses the path
as given. No referenced local PDF path or basename is rendered into the page.

```sh
python -m scripts.offline_research_dashboard --financial-config /path/to/financial.json --max-financial-rows 20 --output /tmp/financial_review_dashboard.html
```

The optional row limit is an integer from 1 to 500, default 20. Counts and an
explicit omitted-row count always cover the complete extraction. `annotations`
must be null or a hash-bound annotation object using the existing
[financial review pipeline](financial-review-pipeline.md) and
[annotation](financial-table-review-annotations.md) contracts; it is
not an arbitrary list or prebuilt result. The existing validators reject stale
hashes or invalid decisions before output. Reviewer names/notes are escaped
caller assertions, not authenticated identities. Accepting a candidate leaves
its original blockers and unknown consolidation scope unchanged. PDF and package
SHA-256 values identify the materials being viewed.

A valid PDF with no numeric candidates displays `no_numeric_candidates`, zero
candidate count and an explicit lack-of-evidence message, never a claim that
financial verification is complete. A malformed/empty file or invalid config
fails instead of replacing a previous page. Structural validation is shown
separately from financial verification and release acceptance, which remain
unverified/not accepted. Set `data_kind` to `SYNTHETIC` only for an invented test
PDF; a real local file is still `UNVERIFIED_LOCAL` until independently verified.

The displayed return difference is SMA test return minus benchmark return in
percentage points, not a geometric relative return or proof of skill. Costs
and slippage use the existing paper engine. Final holdings are marked, not
liquidated. All historical/source/performance verification flags remain false.
The page repeats the limitations on corporate actions, calendar gaps,
tradability and real execution; it provides no trade controls or investment
recommendation.

All dynamic text is HTML-escaped. SVG positions come only from recomputed
finite numeric results. A meta Content Security Policy denies all sources and
scripts, permitting only the exact hash of the static embedded stylesheet.
The responsive layout uses flexible containers and horizontally scrolling
tables on narrow screens. The displayed hashes bind each underlying computed
artifact; they are not an authentication of the HTML file itself.

The existing bounded regular-file JSON reader rejects duplicate keys, malformed
JSON and oversized/nonfinite inputs before rendering. Output is bounded to
2 MiB. Existing schemas also bound nested JSON and market data sizes. All
sections must succeed before atomic replacement of the destination; an invalid
section preserves an existing page. The output cannot overwrite any supplied config or financial PDF,
including resolved or hard-linked aliases, and symbolic-link output targets are
rejected. Temporary files are cleaned on failure. This is not a general
defense against hostile concurrent replacement of parent directories.

```sh
python -m unittest tests.test_offline_research_dashboard -v
```
