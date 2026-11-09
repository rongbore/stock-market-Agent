# Offline batch brief runner

Run the deterministic T09 plan with explicit local trend-report objects:

```sh
python -m scripts.offline_batch_research_runner --plan batch-plan.json --reports reports.json --output batch-result.json
```

`reports.json` is an object mapping planned symbols to inline trend-report
objects, not file paths or commands. Example:

```json
{"000776.SZ":{"symbol":"000776.SZ","dates":["2026-11-05","2026-11-06"],"prices":[10.0,11.0]}}
```

The runner reconstructs the plan using `build_batch_plan` and rejects changes
to job operations, IDs, output paths, status or other contract fields. It does
not use plan-provided paths to write artifacts. The explicit CLI invocation is
the request to perform this local operation; the planner itself still executes
nothing and its `execution_authorized` field is not elevated or repurposed.

Each supplied report must match its job symbol, contain 1–10,000 canonical
ascending unique dates no later than the requested cutoff, and have aligned
finite positive prices. Existing `build_brief` generates the historical summary;
nonfinite derived price changes are also rejected. Missing or invalid input
fails that job while other jobs continue. Unexpected symbols invalidate the
input mapping before processing.

The output contains one result per planned job and explicit success/failure
counts. A successful brief is `COMPLETED_UNVERIFIED`; this means local summary
generation succeeded, not source authentication, historical availability or
investment advice. A mixed or entirely failed run is `COMPLETED_WITH_FAILURES`.
The CLI exits zero when it successfully writes this result bundle, even if some
jobs failed; callers must inspect the counts and per-job statuses. Invalid plan
or mapping structure prevents output entirely. Each JSON input is limited to
20 MiB and the plan to 100 symbols.

Only one JSON bundle is atomically written. Input overwrites and symbolic-link
output targets are rejected. No per-job directories, network calls, models,
paid APIs, schedules, trades or brokerage connections are created. Financial
statements, source timestamps and point-in-time provenance remain unverified.

## Deterministic integrity identifiers

`plan_sha256` binds the complete validated deterministic plan, including its
jobs, operation and proposed artifact paths. Each supplied trend input receives
`input_sha256` before financial input validation, so an invalid symbol, date or
price report still retains its integrity identifier when it is bounded JSON.
Missing inputs have a null hash and `input_hash_status: missing`; rejected JSON
has a null hash and `rejected_noncanonical_json`. A supplied JSON `null` is hashed
and then fails report validation, distinguishing it from an absent input.

The encoding `json_sorted_keys_ascii_compact_v1` uses Python JSON with sorted
object keys, ASCII escapes, compact separators and nonfinite numbers forbidden.
It binds the parsed JSON value, not the original file's spacing or key order.
Integer and floating representations remain distinct. This is a versioned
application encoding, not an RFC 8785 claim. All fields of each report, including
unused metadata, participate in its hash. Results contain no current timestamps,
and repeated identical inputs produce identical bundles without mutating inputs.

Only exact JSON built-in types with string object keys are hashable. Bounds are
32 container levels, 100,000 visited nodes, 1024-bit integers and a conservative
20 MiB encoding budget per plan or report. Deep, cyclic, huge, nonfinite and
non-JSON report inputs fail their own job without a hash; invalid plans fail the
entire run. The CLI also converts excessive JSON parser depth to a validation
failure and leaves an existing output intact.

These hashes identify integrity only. They do not authenticate data publishers,
validate prices or prove data existed at the analysis cutoff. Source and
historical-point-in-time verification flags remain false. No hash operation
fetches outside evidence or authorizes model, network or trading calls.
