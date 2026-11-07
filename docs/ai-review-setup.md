# AI PR review setup (manual, advisory only)

The repository includes a manually dispatched AI review workflow:
`.github/workflows/ai-pr-review-manual.yml`.

## Required repository configuration

In **Settings → Secrets and variables → Actions**:

- Add secret `AI_REVIEW_API_KEY` for the selected model provider.
- Add variable `AI_REVIEW_ENDPOINT` with the provider's HTTPS chat-completions endpoint.
- Add variable `AI_REVIEW_MODEL` with the model identifier.

Do not put credentials in repository variables, source files, PR comments, or workflow inputs. Use a provider endpoint controlled by your organization. The current HTTP client requires HTTPS and blocks redirects; review endpoint allowlisting and outbound network policy before enabling in a production runner.

## Run a review

1. Open **Actions → AI PR review (manual, read only)**.
2. Select **Run workflow** on the default branch.
3. Enter an open PR number targeting `main`.
4. Inspect the run log and download the `ai-pr-review-N` artifact.

## Security and behavior

- The workflow is manually triggered; it does not run automatically on every PR.
- It uses read-only `contents` and `pull-requests` permissions.
- It checks out the default-branch workflow code, never the PR head.
- PR diffs are sent to the configured external model provider. Only enable after reviewing that provider's data handling, retention, and contractual terms.
- Reviews are advisory. Model output is untrusted, cannot approve a PR in GitHub, and cannot merge code.
- Missing credentials, unsupported diff formats, oversized changes, invalid model output, or a changed PR head cause the run to fail closed.
- This workflow does not support autonomous merge. A separate trusted controller and independent policy gates are required.

## Cost control

Each manual run can incur model-provider charges. Run only on PRs that need review and monitor provider usage. No model call is made by the repository merely because this workflow exists.
