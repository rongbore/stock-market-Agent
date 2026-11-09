# Offline batch research plan

Create a bounded plan for explicitly selected A-share symbols:

```sh
python -m scripts.batch_research_plan --symbols 000776.SZ 600519.SS --analysis-date 2026-11-08 --output batch-plan.json
```

The command validates 1–100 unique six-digit `.SZ` or `.SS` symbols and an exact
`YYYY-MM-DD` date. Symbol validation checks format only; it does not establish
that a ticker is listed. Jobs are sorted by symbol, so the same symbol set and
date produce the same plan ID, job IDs and relative artifact paths. IDs and paths
contain only validated symbols and date components, never caller-provided paths.

Every job starts as `PENDING_INPUTS` and requests a per-symbol trend report JSON
for the existing offline `market_research_brief` operation. No report is loaded,
generated, verified, or recommended by the planner. The requested date is not
evidence of historical data availability. Consumers must separately validate
each input's symbol, dates and evidence before executing any work.

The output status is `PLANNED_ONLY`, `jobs_executed` is zero and
`execution_authorized` is false. This is the planning interface for T09, not a
stock screener or batch executor. There are no network, paid model, brokerage,
trading or scheduling calls. The CLI writes one plan JSON atomically, rejects a
symbolic-link output target and creates no job directories. Generated artifact
paths are relative suggestions for a future executor, not files written now.

Validation: `python -m unittest tests.test_batch_research_plan -v`.
