# Offline report archival (v0.2 Day 4)

Use the CLI only after an existing offline report has been generated:

```bash
python -m scripts.report_archive --source results/reports/000776.SZ/2026-11-04 --archive-root results/history --ticker 000776.SZ --analysis-date 2026-11-04
```

The archive stores a SHA-256 content-addressed snapshot and a file hash
manifest. Repeating the same run returns `created: false`. Changed inputs
create a new archive rather than overwriting prior snapshots.

This is an **offline-only primitive**. It does not schedule jobs, fetch live
market data, invoke paid models, submit trades, or claim that archived source
data has been independently verified. Do not store credentials in reports.
Scheduler, retry/backoff and CI artifact integration are separate follow-ups.
