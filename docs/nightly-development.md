# Nightly development policy (v0.2)

- Timezone: Asia/Shanghai (UTC+08:00), permitted development window 21:00–06:00.
- Start with tests, dependency reproducibility, source timestamps and report validation.
- Work on feature branches and submit draft pull requests for human review.
- Never automatically merge to main or run broker transactions.
- Never commit secrets or private positions.
- GitHub Actions test workflow validates pull requests but **does not itself generate code**.
- Scheduled ChatGPT tasks are separate from GitHub Actions and do not guarantee continuous 9-hour coding sessions.
- Check tests, diffs and permissions before approving each PR.
