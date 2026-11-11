# Local snapshots to research inputs

Convert previously saved normalized AKShare Eastmoney/Sina snapshots to the
existing batch pipeline and dashboard. No network, model or brokerage calls occur.

Input JSON requires exactly `schema_version: "0.1"`, `data_kind` (`SYNTHETIC` or
`UNVERIFIED_LOCAL`), `analysis_date` (canonical date), timezone-aware
`evidence_as_of`, explicit `expected_adjustment` (see daily-bar contract), and
`snapshots` mapping 1–100 stock symbols to their inline normalized snapshots.
For example, load an existing file and construct the bounded adapter input:

```python
import json
from pathlib import Path
snapshot = json.loads(Path("snapshot.json").read_text(encoding="utf-8"))
config = {"schema_version": "0.1", "data_kind": "UNVERIFIED_LOCAL",
          "analysis_date": snapshot["end_date"],
          "evidence_as_of": snapshot["retrieved_at"],
          "expected_adjustment": "unadjusted",
          "snapshots": {snapshot["symbol"]: snapshot}}
Path("snapshot-input.json").write_text(json.dumps(config), encoding="utf-8")
```

Confirm the date and adjustment assumptions, then run:

```sh
python -m scripts.snapshot_research_config --input snapshot-input.json --output batch-config.json
python -m scripts.offline_batch_pipeline --input batch-config.json --output research.json
python -m scripts.offline_research_dashboard --batch-config batch-config.json --output dashboard.html
```

The adapter reuses the daily-bar validator for OHLCV, units, unique ascending
dates, explicit adjustment and retrieval/evidence cutoff. It rejects any future
row after analysis_date rather than silently discarding it. Each report supports
at most 10,000 bars; bounded JSON constraints also apply. One invalid snapshot
blocks the adapter and leaves prior output intact. Output cannot replace inputs
or symbolic-link targets and is replaced atomically after validation.

The output is a raw five-field batch config. Each report retains input close
values and `price_basis=single_source_close`, so its summary says single-source
dates and closing price, never a dual-source mean or verified numerical agreement.
Nested `snapshot_provenance_unverified` records canonical snapshot SHA-256,
upstream/interface, retrieval time, evidence cutoff and adjustment. Downstream
batch hashes bind these fields too. The raw snapshot remains separately archived.

Use SYNTHETIC for invented fixtures. UNVERIFIED_LOCAL does not authenticate actual
market data, timestamps or historical availability. Adjusted prices can contain
later corporate actions. Source/PIT flags stay false; no prediction, scheduling
or trading occurs. Real-data accuracy acceptance is still a separate task.
