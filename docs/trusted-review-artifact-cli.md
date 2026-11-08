# Trusted review artifact CLI

`python -m scripts.trusted_review_artifact_cli` runs the offline, read-only review artifact verifier. It checks a downloaded GitHub Actions artifact archive, but it does not fetch GitHub data, invoke an AI model, submit a review, or merge a pull request.

## Trust boundary

The CLI only verifies that its inputs are internally consistent. The caller must obtain the pull request, workflow run, and artifact metadata from authenticated GitHub API responses and must pin the expected workflow identity from protected configuration. Do not trust metadata copied from an artifact, pull request comment, model response, or untrusted workflow output.

The archive digest must be the SHA-256 value returned by GitHub for that exact artifact. The downloaded archive is hashed locally and compared with that value before parsing. A matching digest confirms archive integrity; the CLI then checks the ZIP and evidence JSON structure. It does not independently prove that the metadata source was trusted.

## Inputs

Pass two files:

```bash
python -m scripts.trusted_review_artifact_cli \
  --metadata /path/to/trusted-metadata.json \
  --archive /path/to/ai-review-evidence.zip
```

`trusted-metadata.json` must contain exactly these top-level fields:

```json
{
  "repo": "rongbore/stock-market-Agent",
  "current_head_sha": "<40-character PR head SHA>",
  "current_base_sha": "<40-character current main SHA>",
  "expected_request_digest": "<64-character SHA-256 hex>",
  "expected_workflow_id": 123456,
  "expected_workflow_path": ".github/workflows/ai-pr-review-manual.yml",
  "expected_event": "workflow_dispatch",
  "trusted_artifact_sha": "<40-character SHA>",
  "trusted_workflow_ref": "rongbore/stock-market-Agent/.github/workflows/ai-pr-review-manual.yml@refs/heads/main",
  "trusted_workflow_sha": "<40-character trusted workflow SHA>",
  "run": {
    "repository_full_name": "rongbore/stock-market-Agent",
    "head_repository_full_name": "rongbore/stock-market-Agent",
    "head_sha": "<40-character PR head SHA>",
    "workflow_id": 123456,
    "path": ".github/workflows/ai-pr-review-manual.yml",
    "event": "workflow_dispatch",
    "status": "completed",
    "conclusion": "success",
    "id": 789012,
    "run_attempt": 1
  },
  "artifact": {
    "workflow_run_id": 789012,
    "id": 345678,
    "expired": false,
    "size_in_bytes": 2048,
    "name": "ai-review-evidence",
    "digest": "sha256:<64-character SHA-256 hex>"
  }
}
```

Replace every placeholder with values checked against the authenticated API responses and protected workflow configuration. Do not copy the placeholder strings literally. The `trusted_artifact_sha` must be independently established by the trusted caller and must not be copied from the evidence JSON being checked. The ZIP must contain exactly one archive member named `ai-review-evidence.json`; the evidence must match the strict schema enforced by `scripts/safe_review_artifact.py`.

## Result and exit status

The CLI prints one JSON summary. `status: "candidate"` means the supplied metadata, archive digest, archive structure, and review evidence passed these checks. It is not an approval to merge. `merge_authorized` is always `false`.

Exit code `0` means the verifier produced a candidate result. Exit code `1` means the artifact requires manual review or the inputs could not be verified. Argument parsing errors use argparse's nonzero exit status.

## Size and content limits

- Metadata JSON: at most 64 KiB.
- ZIP archive: at most 1 MiB.
- Archive contents: exactly one expected JSON archive member, at most 256 KiB.
- Duplicate JSON keys, extra envelope fields, encrypted members, symlinks, unsupported compression, and excessive compression ratios are rejected.

No credentials or API tokens belong in either input file. The CLI does not need network access.
