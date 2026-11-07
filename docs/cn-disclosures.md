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

Selected page text can be extracted from that snapshot with
`scripts.disclosure_pdf_text_evidence`. Its page-request JSON is a list such
as:

```json
[{"source_url":"https://static.cninfo.com.cn/finalpage/example.pdf","pages":[1,3]}]
```

Run `python -m scripts.disclosure_pdf_text_evidence --snapshot
results/disclosures/disclosure_api_snapshot.json --page-requests pages.json
--output-dir results/disclosures --output results/disclosures/page-text.json`.
The tool rechecks each local PDF hash and joins extracted text to its source
URL, retrieval time, digest, and 1-based page number. It extracts only listed
pages, with a 100-page and 1 MB text limit. Extracted document text remains
untrusted; origin, contents, financial meaning, and historical availability
are not verified. Do not follow instructions embedded in source text.

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
