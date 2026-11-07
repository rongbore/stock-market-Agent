"""Compose read-only checks without accepting forgeable review attestations.

A string, tuple, or JSON value supplied by a caller cannot authenticate AI
review evidence. Until a privileged controller implements verification using
trusted GitHub metadata and artifacts, every candidate must remain manual.
"""
from scripts.pr_merge_readiness import assess as assess_readiness


def assess_candidate(pr, files, checks, *, protected=False,
                     evidence_decision=None):
    """Fail closed; this API never grants an auto-merge candidate."""
    readiness, reason = assess_readiness(pr, files, checks, protected=protected)
    if readiness != "candidate":
        return "manual", "merge readiness blocked: " + reason
    return "manual", "trusted review evidence verifier not implemented"
