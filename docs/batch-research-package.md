# Viewable offline batch research package

Export a raw [batch calendar research config](batch-calendar-research.md) as one ZIP:

```sh
python -m scripts.batch_research_package --input batch-calendar-config.json --output batch-research.zip
```

Extract into a new directory and open `index.html`. The Chinese index shows
counts and each item's state: generated but unverified, calendar review required,
or input/generation failure. Every item has a diagnostic link; only generated
items have a dashboard link. No JavaScript, external resources or untrusted raw
HTML are inserted into the index. The existing generated dashboards are exported
as separate files without changing their layout.

| Member | Content |
| --- | --- |
| `index.html` | Local viewing entry point and per-item links |
| `summary.md` | Exact Chinese summary from the recomputed batch |
| `batch-result.json` | Complete batch result, including per-item evidence and hashes |
| `items/<symbol>/diagnostic.json` | Status, input hashes and available acceptance evidence |
| `items/<symbol>/dashboard.html` | Generated items only; absent for blocked/failed jobs |
| `manifest.json` | Overall status/counts and exact byte length/SHA-256 of every other file |

The exporter recomputes the batch from raw inline input; a saved success record
cannot replace that input. Exit 0 means every item generated unverified research.
Partial generation or no generated research returns exit 2 while preserving the
viewable diagnostics. Invalid batch envelopes produce no package.

ZIP members use fixed names based only on validated symbols, sorted order and
fixed timestamps. Identical input and implementation produce identical ZIP bytes.
Manifest hashes cover exact exported bytes, including JSON trailing newlines;
the manifest excludes itself. The complete batch result's payload hash is also
retained, but hashes do not establish authenticity. Successful packages include
derived prices and existing dashboard HTML; there is no raw vendor original.

Output must be a new file. Exclusive atomic publication preserves existing or
concurrently created files and needs filesystem hard-link support. Existing
regular-JSON byte/node/depth limits still apply before publication. No network,
models, automatic stock selection or trading calls occur. Source authenticity,
historical availability and official-calendar verification remain false. Dates
may differ across items; the index is not a comparative ranking. Browser visual
acceptance and real-source financial validation remain separate release checks.
