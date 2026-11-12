# Opt-in AKShare collection to research

With optional AKShare dependencies installed and network access permitted:

```sh
python -m scripts.collect_market_research --symbol 000776.SZ --start-date 2026-11-02 --end-date 2026-11-06 --upstream eastmoney --allow-network --output collection.json
```

Select one symbol, an explicit date window of at most 366 days and `eastmoney`
or `sina`. Unadjusted data is requested. `--allow-network` is mandatory; no model,
brokerage or paid inference is invoked. Underlying AKShare provider behavior,
rate limits, API availability and optional package installation still apply.

The new-file-only JSON result contains the collected snapshot, source-labelled
batch raw config, research result and embedded dashboard HTML after all stages
succeed. To view HTML, extract `dashboard_html` from the JSON to a separate local
HTML file; `batch_config` is also usable by the existing dashboard CLI. Source
and historical availability are never verified by successful collection.

Failures produce a small diagnostic artifact and exit code 2, identifying the
collection or validation stage. Raw exceptions/provider bodies are not written.
Invalid requests and existing output paths fail before collection. Atomic
exclusive file creation prevents clobbering prior evidence, including concurrent
creation; the destination filesystem must support hard links. Caller interruption
and write failures may terminate without an artifact. Vendor timeout/retry behavior
is inherited from AKShare; this wrapper adds no time-bound transport guarantee.

Tests inject synthetic provider responses or failures and exercise the actual
offline stages. They are not successful live-source acceptance. Live collection,
financial accuracy and historical availability require a separate real-data run.
