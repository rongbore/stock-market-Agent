# A-share disclosure metadata — v0.2 groundwork

The disclosure adapter accepts A-share symbols (`000776.SZ`, `600519.SS`),
announcement title, provider, HTTPS source URL, and announcement date. Its
opt-in `--download-originals` mode also retrieves candidate CNINFO PDFs from
the exact `static.cninfo.com.cn/finalpage/` host and records a SHA-256 digest,
retrieval timestamp, and relative artifact path in the JSON snapshot.

Example:

```sh
python -m scripts.disclosure_api \
  --endpoint 'https://www.cninfo.com.cn/<approved-query-endpoint>' \
  --source cninfo --analysis-date 2026-11-07 --symbol 000776.SZ \
  --output-dir results/disclosures --download-originals
```

The PDF fetch has a 20 MiB response limit, checks the PDF header and EOF
marker, and refuses redirects. It uses no API key. Downloads and SHA-256
digests make the retrieved bytes traceable; they do not prove publisher
authenticity or validate the financial contents.

**Caution:** A disclosure date alone does not establish when an announcement
became available to the market. Even if a timestamp is supplied, this
normalizer cannot independently verify it; therefore
`publication_time_verified=false` and
`same_day_historical_eligibility=unknown` are always retained.

For historical research, do not treat a same-day announcement as eligible
without checking its original exchange/provider publication time. A separate
trusted adapter and source verification process are required.

The adapter fetches only when explicitly run. It makes no model or brokerage
calls and uses no paid APIs. Run `python -m unittest discover -s tests -v`.
