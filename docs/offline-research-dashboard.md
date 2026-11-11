# Local read-only research dashboard (T10 prototype)

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

At least one of `--batch-config` and `--evaluation-config` is required. Either
alone creates its respective section; providing both creates a combined page.
The arguments are **raw input configurations**, not previously computed result
artifacts. `build_pipeline` and `build_evaluation_artifact` revalidate and
recompute results before rendering. Supplied output metrics are never accepted
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
section preserves an existing page. The output cannot overwrite either config,
including resolved or hard-linked aliases, and symbolic-link output targets are
rejected. Temporary files are cleaned on failure. This is not a general
defense against hostile concurrent replacement of parent directories.

```sh
python -m unittest tests.test_offline_research_dashboard -v
```
