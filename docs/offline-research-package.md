# Offline calendar-gated research package

Generate an inspectable ZIP directly from the same raw config used by the
[offline calendar acceptance CLI](offline-calendar-acceptance.md):

```sh
python -m scripts.offline_research_package --input acceptance-config.json --output research-package.zip
```

Use the synthetic config recipe in that guide for an offline smoke test. This
command recomputes structural validation, calendar coverage, research and HTML
from raw input. It never accepts a saved `MATCH` record as proof and makes no
network, model or brokerage calls.

On success (exit 0), extract the package into a new directory and open
`dashboard.html`. No manual extraction of an HTML string from JSON is needed.

| File | Purpose |
| --- | --- |
| `README.txt` | Unverified-data notice and viewing instructions |
| `acceptance.json` | Recomputed date coverage, snapshot/calendar/config hashes |
| `research.json` | Research pipeline result with existing evidence labels |
| `batch-config.json` | Derived single-source config bound to the snapshot hash |
| `summary.md` | Exact UTF-8 Chinese summary from the research result |
| `dashboard.html` | Existing self-contained, read-only dashboard |
| `manifest.json` | Status, data declaration, and byte length/SHA-256 of each other file |

Date disagreement produces exit 2 and a diagnostic-only package containing
`README.txt`, `acceptance.json` and `manifest.json`. No research, prices config,
summary or dashboard is exported. Suspensions may explain a missing session;
review the evidence rather than synthesizing bars or editing dates to force a pass.
Invalid input or downstream generation errors leave no package.

Files have fixed names, stable order and ZIP timestamps, so identical raw input
and implementation produce identical ZIP bytes. Manifest hashes cover the **exact
exported bytes**, including JSON trailing newlines. The manifest excludes itself
from its file list; it is not a cryptographic signature. It also records the
combined gated-result payload hash from the underlying generation step. Hashes
bind content and do not establish authenticity, authorship or historical availability.

The output must be a new file, including when another writer races publication.
Temporary files are cleaned after ordinary errors, and the destination filesystem
must support hard links. Input has the existing bounded regular-JSON checks.
Successful packages contain derived prices; they are research artifacts, not a
license to redistribute vendor data. No raw vendor response or official evidence
is added. Synthetic inputs remain labelled synthetic; all source/PIT/calendar
verification flags remain false. The dashboard retains its existing labels;
calendar coverage must be reviewed in `acceptance.json`.

This exports existing HTML without changing its layout. Archive integrity and
content are tested; browser visual acceptance and the real-source requirements
of the [v0.2 release gate](v02-release-evidence-gate.md) remain separate.
