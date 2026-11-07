# AI PR review setup

## Required repository configuration

In **Settings → Secrets and variables → Actions** configure:

- Secret `AI_REVIEW_API_KEY`: API key for the selected model provider.
- Variable `AI_REVIEW_ENDPOINT`: provider HTTPS chat-completions endpoint.
- Variable `AI_REVIEW_MODEL`: provider model identifier.

Never put credentials in variables, source files, PR comments, or workflow inputs.

## Automatic and manual operation

The `AI PR review (read only)` workflow runs on same-repository pull requests when opened, reopened, synchronized, or marked ready for review. It can also be started manually from Actions with a PR number.

The workflow is triggered with `pull_request_target` so it loads the trusted workflow definition from the base branch. It explicitly checks out only the repository default branch and never checks out or executes PR code. Permissions are limited to `contents: read` and `pull-requests: read`. Fork PRs are skipped to prevent unexpected external model calls and spending.

## Data sharing and cost

The PR file patches are sent to the configured external model provider for review. Confirm provider data handling, retention, and contractual terms before enabling. Each review may incur API charges; synchronization events can trigger repeated reviews. Concurrency cancels superseded runs for the same PR.

## Results

The workflow uploads `ai-review-result.json` as a 14-day artifact. It contains an advisory verdict, summary, findings, and a fixed failure reason when blocked. The model's verdict does not approve, merge, or authorize a PR.

## Security boundary

- The model output is untrusted and advisory only.
- The workflow cannot write PR reviews, modify branches, or merge.
- Missing credentials, unsupported diffs, oversized changes, invalid model output, and stale PR head SHA fail closed.
- Fork PRs are not sent to the external model by this workflow.
