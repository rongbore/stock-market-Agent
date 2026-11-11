# One-command offline chronological evaluation

Run the supplied **SYNTHETIC** fixture from the repository root:

```sh
python -m scripts.sma_evaluation_cli --input examples/backtest/SYNTHETIC_sma_oos_config.json --output /tmp/SYNTHETIC_sma_evaluation.json
```

This fixture is invented test data, including invented retrieval timestamps,
volumes and prices. Its AKShare-compatible metadata names an expected input
shape, not an actual provider retrieval. The `akshare_version` marker explicitly
says `SYNTHETIC_FIXTURE_NOT_FETCHED`. The ticker is only an identifier; these are
not prices or results for that stock. Cost assumptions are hypothetical, not
claims about current tax, broker or exchange rules. Do not use these results as
market research or investment advice.

The command invokes the existing chronological evaluator unchanged and writes
one JSON artifact containing train/test/benchmark paper runs, signals, fills,
close marks, fees, observed-period return, drawdown and arithmetic return
comparison. It does not fetch data, call a model, optimize parameters or trade.
Train/test accounts remain independent, training closes serve only as test
warmup, and the benchmark uses the same test interval and execution settings.

The input has exactly four top-level keys:

| Key | Required value |
| --- | --- |
| `schema_version` | `"0.1"` |
| `data_kind` | `"SYNTHETIC"` or `"UNVERIFIED_LOCAL"`; a caller declaration, not authentication |
| `snapshot` | Inline normalized AKShare daily snapshot with the exact keys below |
| `settings` | All explicit evaluator arguments in the next table |

The snapshot has exactly `schema_version`, `symbol`, `source`, `upstream`,
`interface`, `akshare_version`, `adjust`, `price_unit`, `volume_unit`, `start_date`,
`end_date`, `retrieved_at`, `source_content_verified`,
`historical_point_in_time_verified`, and `records`. AKShare version must be a
nonempty string of at most 100 characters; it is metadata, not a provenance
verification. Each record has exactly `date`, `open`, `high`, `low`, `close`,
`volume`. The underlying [data contract](backtest-data-contract.md) validates
source/interface, units, finite OHLCV, date order and timing. Verification flags
must explicitly remain false.

| Settings keys | Meaning |
| --- | --- |
| `evidence_as_of`, `expected_adjustment` | Timezone-aware evidence cutoff; only `"unadjusted"` is supported |
| `train_end`, `test_start`, `window` | Fixed observed chronological split and SMA window; no test-driven search |
| `initial_cash`, `board_lot_size` | Explicit independent account capital and lot size |
| `commission_bps`, `minimum_fee`, `sell_tax_bps`, `slippage_bps` | Explicit execution cost assumptions, including when zero |

No setting has a default, and unknown or missing keys are rejected at every
listed schema level. Duplicate JSON keys, unsupported JSON types, nonfinite
numbers, oversized integers or excessive nesting/nodes/bytes are rejected.
The CLI permits at most 500 inline daily bars; the lower-level evaluator's
separate 2000-bar limit is unchanged. The shared canonical encoder additionally
bounds both input and output to 20 MiB and 100000 JSON nodes, depth at most 32.
All validation and serialization finish before an existing result is replaced.

The artifact declares data kind and limitations prominently, with all source,
historical-availability and performance-verification flags false. It includes:

- `config_input_sha256`: SHA-256 of canonical input JSON, not raw file bytes.
- `artifact_payload_sha256`: SHA-256 of the entire artifact excluding only this
  hash field itself. The file's final newline is outside this hash.
- `hash_encoding`: `json_sorted_keys_ascii_compact_v1`, the shared finite/bounded
  encoder with sorted keys, ASCII escaping and compact separators. This is not
  RFC 8785; numeric spellings represented by distinct Python types can hash
  differently. Whitespace and key order alone do not change the canonical hash.

Identical valid inputs produce identical result bytes, including the final
newline; no runtime timestamp or path is embedded. A hash binds the supplied
content but does not authenticate data, publisher or a reviewer.

Output uses a temporary file in its destination directory followed by atomic
replacement. An invalid config preserves an existing output. The config cannot
be overwritten via the same path, resolved alias or existing hard link; symbolic
link output targets are rejected. Temporary output is cleaned on failure.
Atomic replacement is not a claim of crash durability or a general defense
against hostile concurrent parent-directory replacement.

Historical availability, calendars, corporate actions, tradability and exact
broker settlement remain unverified/unmodeled. Read
[chronological evaluation](sma-out-of-sample.md) and
[benchmark definitions](paper-benchmark-risk.md) before interpreting outputs.

```sh
python -m unittest tests.test_sma_evaluation_cli -v
```
