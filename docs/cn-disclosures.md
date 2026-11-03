# A-share disclosure metadata — v0.2 groundwork

This offline normalizer accepts A-share symbols (`000776.SZ`, `600519.SS`),
announcement title, provider, HTTPS source URL, and announcement date.
An optional timezone-aware publication timestamp can be carried through.

**Caution:** A disclosure date alone does not establish when an announcement
became available to the market. Even if a timestamp is supplied, this
normalizer cannot independently verify it; therefore
`publication_time_verified=false` and
`same_day_historical_eligibility=unknown` are always retained.

For historical research, do not treat a same-day announcement as eligible
without checking its original exchange/provider publication time. A separate
trusted adapter and source verification process are required.

No live exchange access, model calls, brokerage access, or paid APIs.
Run `python -m unittest discover -s tests -v`.
