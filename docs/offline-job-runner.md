# Offline job runner (v0.2 Day 4)

The runner executes an explicitly provided local command **without a shell**.
It limits retries (1–5), timeout (1–3600 seconds), and linear retry delay
(0–30 seconds). Logs contain timestamps, statuses and exit codes, but not
command arguments, stdout, stderr or secrets.

Example using a harmless local command:

```bash
python -m scripts.offline_job_runner --attempts 2 --timeout 30 --delay 1 --result results/job-status.json -- python -c "print('offline smoke test')"
```

This component is not a scheduler, service or daemon. It does not fetch
live data, trigger paid inference, connect to a broker or place trades.
Never pass credentials in command arguments. A future scheduler must use
an explicit allowlist of offline tasks and a separate deployment review.
