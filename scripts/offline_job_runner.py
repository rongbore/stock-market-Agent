"""Offline subprocess runner with bounded retries; no scheduler or shell execution."""
import argparse
import json
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path


def run_job(command, *, attempts=3, timeout=120, delay=1, runner=None, sleep=None):
    if not isinstance(command, (list, tuple)) or not command or not all(
        isinstance(x, str) and x for x in command
    ):
        raise ValueError("command must be a nonempty argument vector")
    if type(attempts) is not int or not 1 <= attempts <= 5:
        raise ValueError("attempts must be between 1 and 5")
    if type(timeout) is not int or not 1 <= timeout <= 3600:
        raise ValueError("timeout must be between 1 and 3600 seconds")
    if type(delay) is not int or not 0 <= delay <= 30:
        raise ValueError("delay must be between 0 and 30 seconds")
    runner = runner or subprocess.run
    sleep = sleep or time.sleep
    events = []
    for index in range(1, attempts + 1):
        started = datetime.now(timezone.utc).isoformat()
        try:
            result = runner(command, timeout=timeout, check=False,
                            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            returncode = result.returncode
            status = "success" if returncode == 0 else "failed"
        except subprocess.TimeoutExpired:
            returncode, status = None, "timeout"
        except OSError:
            returncode, status = None, "launch_error"
        events.append({"attempt": index, "started_at_utc": started,
                       "status": status, "returncode": returncode})
        if status == "success":
            break
        if index < attempts:
            sleep(delay * index)
    return {"success": events[-1]["status"] == "success", "attempts": events}


def main(argv=None):
    parser = argparse.ArgumentParser(description="Run a local offline task with bounded retries")
    parser.add_argument("--attempts", type=int, default=3)
    parser.add_argument("--timeout", type=int, default=120)
    parser.add_argument("--delay", type=int, default=1)
    parser.add_argument("--result", type=Path, required=True)
    parser.add_argument("command", nargs=argparse.REMAINDER,
                        help="command arguments after -- (no shell)")
    args = parser.parse_args(argv)
    command = args.command[1:] if args.command[:1] == ["--"] else args.command
    try:
        outcome = run_job(command, attempts=args.attempts,
                          timeout=args.timeout, delay=args.delay)
    except ValueError as exc:
        parser.error(str(exc))
    args.result.parent.mkdir(parents=True, exist_ok=True)
    args.result.write_text(json.dumps(outcome, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"success": outcome["success"],
                      "attempt_count": len(outcome["attempts"])}))
    return 0 if outcome["success"] else 1


if __name__ == "__main__":
    sys.exit(main())
