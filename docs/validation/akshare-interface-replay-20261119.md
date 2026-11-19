# AKShare rename recovery and partial live replay — 2026-11-19

## Actual failure

[Actions run 44283238874](https://github.com/rongbore/stock-market-Agent/actions/runs/44283238874)
failed on 2026-11-18 at main `761866af7fb1bb2372d9ae841d7716b9c4ca9242`.
Job `134729171146` called the removed `stock_zh_a_hist` attribute. The raw
AttributeError escaped the supported fetch exceptions, preventing the other
provider from being attempted. This was a live dependency incompatibility,
not an offline unit-test failure.

The [official AKShare changelog](https://akshare.akfamily.xyz/changelog.html)
records the Eastmoney/Sina rename in 1.20.46 and the Sina hist rename in 1.20.64.
The fix preserves actual invoked names, explicit daily parameters and the
Eastmoney lot/Sina share volume units; it does not relabel new calls as legacy.

## Actual post-fix check

An isolated environment installed AKShare **1.20.65**. With `ak.set_timeout(10)`,
run the fixed dual-upstream code for `000776.SZ`, 2026-11-10 through 2026-11-17:

| Result | Observation |
| --- | --- |
| Overall dual check | exit 1; **not accepted** |
| Eastmoney | failed, fixed `response_or_validation` diagnostic, no snapshot |
| Sina | success; 6 rows through actual `stock_zh_a_hist_sina` |
| Raw attribute crash | did not recur; other provider was attempted |
| Cross-source agreement | false; not compared with two successful snapshots |

The result does not establish Eastmoney availability or exact cause of its
response/validation failure. No error message was copied into committed evidence.
No automated fallback to a different interface occurs after a selected API call
fails; only a missing attribute selects a documented alternative name.

The successful Sina snapshot was also passed through the combined local-manifest
and compatibility candidate. It generated one offline batch research package,
CLI exit 0, with six ZIP members and successful ZIP integrity checks.
For this **pipeline replay only**, calendar sessions were copied from the returned
vendor dates and explicitly labelled as circular input, not independent evidence.
This proves the file-to-package path runs; it does not establish session completeness.

See [machine-readable results and hashes](akshare-interface-replay-20261119.json).
The local-manifest feature and compatibility fix were tested together before
merge; the record identifies both local commits. Raw vendor rows and ZIP were
not committed. Retrieval time, snapshot JSON hash and package ZIP hash are recorded.
All source, historical availability and release-verification claims remain false.

## Reproduction boundary

Use the exact optional dependency version to repeat the live transport check:

```python
import akshare as ak
from scripts.akshare_dual_smoke import run
ak.set_timeout(10)
code = run('000776.SZ', '2026-11-10', '2026-11-17', 'results/interface-replay')
```

Only run when intentionally allowing read-only vendor requests. Later results
may differ with provider availability or changed vendor data. Do not reuse this
single-source success as two-source acceptance or official calendar verification.
No paid models, secrets or brokerage calls were used.
