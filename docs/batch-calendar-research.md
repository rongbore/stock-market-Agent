# Batch local calendar-gated research

Run 1–20 explicitly selected local snapshot jobs with independent calendars,
evidence cutoffs, adjustment declarations and data labels:

```sh
python -m scripts.batch_calendar_research --input batch-calendar-config.json --output batch-calendar-result.json
```

The input has exactly `schema_version: "0.1"` and an `items` list. Every item has
exactly `symbol` and `config`; `config` is the full raw object accepted by the
[calendar acceptance CLI](offline-calendar-acceptance.md). Job symbols must be
unique canonical six-digit `.SZ` / `.SS` identifiers and match each snapshot.
Format validation does not establish whether an instrument is listed.

Starting from the synthetic `acceptance-config.json` recipe in that guide, make
a two-job **synthetic** demo (same invented data, not an actual comparison):

```sh
python - <<'PY'
import copy
import json
from pathlib import Path
first = json.loads(Path('acceptance-config.json').read_text())
second = copy.deepcopy(first)
second['snapshot']['symbol'] = '600519.SS'
second['calendar']['exchange'] = 'SS'
config = {'schema_version': '0.1', 'items': [
    {'symbol': first['snapshot']['symbol'], 'config': first},
    {'symbol': '600519.SS', 'config': second}
]}
with open('batch-calendar-config.json', 'x', encoding='utf-8') as stream:
    json.dump(config, stream)
PY
python -m scripts.batch_calendar_research --input batch-calendar-config.json --output batch-calendar-result.json
```

Jobs run sequentially in sorted symbol order. A malformed envelope, duplicate
job symbol, or more than 20 jobs fails before execution. Once the envelope is
valid, invalid raw data, a symbol mismatch or downstream generation error becomes
a sanitized `FAILED_INPUT_OR_GENERATION` entry and does not suppress other jobs.
Raw exception messages are never embedded in the result. Calendar disagreements
retain their exact missing/unexpected dates in nested acceptance evidence and
produce `REVIEW_REQUIRED` with no research or dashboard for that item.

| Overall status | Meaning | Exit |
| --- | --- | --- |
| `ALL_RESEARCH_GENERATED_UNVERIFIED` | Every item generated unverified research | 0 |
| `PARTIAL_RESEARCH_UNVERIFIED` | Some items generated, at least one blocked/failed | 2 |
| `NO_RESEARCH_GENERATED` | Every item blocked or failed | 2 |

The JSON includes per-item status and canonical input/snapshot/calendar hashes,
counts of generated/calendar-blocked/failed items, a deterministic Chinese
`summary_markdown`, and an outer payload hash. The batch input hash binds the
original submitted job order, while output items and summary rows are sorted.
Hashes of invalid input identify only those supplied bytes/values, not valid or
authentic evidence. Successful item results include derived prices and embedded
HTML. A batch may contain different dates and data declarations; no common
as-of date, cross-stock comparability, ranking or stock selection is inferred.

Inputs use the existing bounded regular-JSON loader with duplicate-key rejection.
Canonical input and output retain existing byte/node/depth limits; an overly large
aggregate artifact fails without publication even if some jobs already ran.
The output must be a new file. Exclusive atomic publication protects an existing
or concurrent output and requires filesystem hard-link support. Temporary files
are cleaned after ordinary write errors. No external files are read by the jobs,
no network/model/brokerage/scheduling calls occur, and all source authenticity,
historical availability and official-calendar verification flags stay false.

This is an offline batch executor, not an automated stock screener or financial
accuracy acceptance. Successful synthetic tests do not meet real-data release gates.
