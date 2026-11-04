"""Offline merge-safety diagnostics; never performs a merge or network request."""
import argparse
import json
import sys

from scripts.branch_protection_audit import audit_repository_state
from scripts.pr_merge_readiness import assess


def report(payload):
    if not isinstance(payload, dict):
        return {"ready": False, "decision": "manual",
                "blockers": ["invalid report input"]}
    blockers = []
    rulesets = payload.get("rulesets")
    protected, reason = audit_repository_state(rulesets, payload.get("legacy_protection"))
    if not protected:
        blockers.append(reason)
    decision, detail = assess(
        payload.get("pr"), payload.get("files"), payload.get("checks"),
        protected=protected,
    )
    if decision != "candidate":
        blockers.append(detail)
    return {"ready": False, "decision": "manual", "blockers": list(dict.fromkeys(blockers)),
            "note": "Read-only diagnostic; effective protection and merge-time checks are not implemented."}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input", nargs="?", default="-", help="JSON input path, or - for stdin")
    parser.add_argument("--strict", action="store_true",
                        help="exit nonzero while merge readiness is unverified")
    args = parser.parse_args(argv)
    try:
        if args.input == "-":
            payload = json.load(sys.stdin)
        else:
            with open(args.input, encoding="utf-8") as stream:
                payload = json.load(stream)
        result = report(payload)
    except (OSError, ValueError, TypeError):
        result = {"ready": False, "decision": "manual",
                  "blockers": ["unreadable or invalid JSON input"]}
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 2 if args.strict and not result["ready"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
