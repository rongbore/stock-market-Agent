# Offline calendar acceptance

Validate a saved AKShare-format snapshot against an explicit local calendar without
network access, optional AKShare installation, models or brokerage access:

```sh
python -m scripts.calendar_acceptance_cli --input acceptance-config.json --output acceptance-result.json
```

The config requires exactly these keys:

| Key | Meaning |
| --- | --- |
| `schema_version` | `"0.1"` |
| `data_kind` | Caller declaration: `SYNTHETIC` or `UNVERIFIED_LOCAL` |
| `snapshot` | Full normalized snapshot with existing source/interface/units metadata and OHLCV records |
| `calendar` | Explicit calendar in [collection calendar format](collect-market-research.md#explicit-calendar-coverage-gate) |
| `evidence_as_of` | Timezone-aware evidence cutoff at or after snapshot retrieval |
| `expected_adjustment` | Explicit `unadjusted`, `forward_adjusted` or `backward_adjusted`, matching snapshot |

The existing backtest data contract validates prices, units, row ordering,
requested bounds, verification flags and daily-bar closure before date comparison.
Calendar source authenticity and suspensions remain unverified. The data declaration
is caller-supplied, not inferred. No historical availability or strategy performance
is established, and adjusted series are not made safe for historical simulation.

## Reproducible synthetic smoke test

Generate a config from the repository's **synthetic** fixture. The sessions below
are copied from fixture bars purely to test the mechanism; this is circular test
data and cannot establish real-world completeness:

```sh
python - <<'PY'
import json
from pathlib import Path
original = json.loads(Path('examples/backtest/SYNTHETIC_sma_oos_config.json').read_text())
s = original['snapshot']
config = {
    'schema_version': '0.1', 'data_kind': 'SYNTHETIC', 'snapshot': s,
    'evidence_as_of': original['settings']['evidence_as_of'],
    'expected_adjustment': original['settings']['expected_adjustment'],
    'calendar': {
        'schema_version': '0.1', 'exchange': s['symbol'][-2:],
        'start_date': s['start_date'], 'end_date': s['end_date'],
        'source': 'SYNTHETIC fixture dates; not independent evidence',
        'sessions': [r['date'] for r in s['records']]
    }
}
with open('acceptance-config.json', 'x', encoding='utf-8') as stream:
    json.dump(config, stream)
PY
python -m scripts.calendar_acceptance_cli --input acceptance-config.json --output acceptance-result.json
```

Exit 0 means `MATCH` against only the supplied calendar. Remove one snapshot row
without changing calendar sessions and rerun with a new output filename to get
exit 2 and `REVIEW_REQUIRED`, including exact missing dates. Unexpected dates also
require review. Do not fill bars or remove calendar sessions to force real data to
pass; investigate suspensions, provider omissions or an incorrect calendar.

Malformed input raises a validation error before any output is created. Input is
bounded by the existing offline JSON byte limit, duplicate keys are rejected,
and non-regular files are rejected. Outputs must be new files; atomic exclusive
publication preserves existing/concurrently created evidence. The destination
filesystem must support hard links. Write failures or interruption may leave no
artifact. No raw exception or provider response is embedded in the record.

The deterministic record contains canonical JSON SHA-256 hashes of config,
snapshot, calendar and artifact payload (excluding its own hash). It stores no
raw prices. Hashes bind content, not authenticity. All verification flags stay
false. No collection, research generation or trading is performed by this CLI.
