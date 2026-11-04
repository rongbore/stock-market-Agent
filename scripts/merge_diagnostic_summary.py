"""Write a safe GitHub Actions summary for the read-only protection diagnostic."""
import json
import os
import sys
from pathlib import Path


def render(payload):
    blockers = payload.get("blockers") if isinstance(payload, dict) else None
    if not isinstance(blockers, list) or not blockers:
        blockers = ["Diagnostic result unavailable or invalid"]
    lines = [
        "## Main branch protection diagnostic",
        "",
        "**Auto-merge remains disabled.** This summary is informational only.",
        "",
        "**Blockers:**",
    ]
    for blocker in blockers:
        if not isinstance(blocker, str):
            blocker = "Invalid blocker record"
        safe = blocker.replace("\r", " ").replace("\n", " ")
        safe = "".join(c if 32 <= ord(c) <= 126 else " " for c in safe)
        safe = safe.replace("<", "&lt;").replace(">", "&gt;")
        lines.append("- " + safe[:250])
    lines += ["", "A green diagnostic run does not authorize merging.", ""]
    return "\n".join(lines)


def main(argv=None):
    path = Path((argv or sys.argv[1:])[0])
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        payload = None
    summary = render(payload)
    destination = os.environ.get("GITHUB_STEP_SUMMARY")
    if destination:
        with open(destination, "a", encoding="utf-8") as stream:
            stream.write(summary)
    else:
        print(summary)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
