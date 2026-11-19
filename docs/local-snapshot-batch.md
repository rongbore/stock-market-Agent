# Batch ZIP from existing local snapshot files

Use a small manifest instead of copying snapshot and calendar objects into a
large inline config:

```sh
python -m scripts.local_snapshot_batch --input samples/manifest.json --output batch-research.zip
```

Example manifest (paths are relative to this manifest file, not the shell's
working directory):

```json
{
  "schema_version": "0.1",
  "data_kind": "UNVERIFIED_LOCAL",
  "evidence_as_of": "2026-11-18T16:00:00+08:00",
  "expected_adjustment": "unadjusted",
  "items": [
    {"symbol": "000776.SZ", "snapshot_path": "000776-snapshot.json", "calendar_path": "sz-calendar.json"},
    {"symbol": "600519.SS", "snapshot_path": "600519-snapshot.json", "calendar_path": "ss-calendar.json"}
  ]
}
```

The snapshot files must contain raw normalized AKShare-format snapshot JSON,
not saved research results or acceptance records. Calendar files use the
[explicit calendar format](collect-market-research.md#explicit-calendar-coverage-gate).
No files are discovered automatically. The manifest requires exactly the shown
keys, 1–20 unique symbols, relative file paths, an explicit supported adjustment,
a timezone-aware cutoff, and `SYNTHETIC` or `UNVERIFIED_LOCAL`. The common data
label, cutoff and adjustment apply to every item; use separate manifests when
those declarations differ.

Every named JSON file is read with the existing bounded regular-file loader.
Missing files or malformed/duplicate-key JSON stop before package generation and
produce no output. Semantic snapshot/calendar errors remain isolated by the
existing batch runner: valid jobs can still generate pages while invalid jobs
retain diagnostics. Partial generation or no generated research returns exit 2;
only all-generated unverified research returns exit 0. Package contents and
viewing instructions are unchanged; see [batch ZIP guide](batch-research-package.md).

Hashes in the resulting package bind the loaded JSON content and resulting
inline config using the existing canonical encoding. They do **not** hash the
manifest's raw bytes, authenticate filenames/paths, or establish source origin.
Two paths containing identical JSON values can produce identical packages.
Paths may explicitly reference relative parent directories; this is not a
filesystem confinement mechanism. No directory scanning, network collection,
model calls, stock selection or trading is performed.

Output must be a new file and cannot target the manifest or a named source file.
Exclusive atomic publication preserves an existing/concurrent output and needs
filesystem hard-link support. Input/output byte, node and depth limits remain
those of the existing offline modules. Source authenticity, historical
availability and official-calendar verification stay false.
