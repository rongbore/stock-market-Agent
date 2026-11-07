"""Compose independent read-only checks; never authorize or perform a merge.

This module deliberately does not trust an AI-produced authentication flag.
The caller must supply a separately verified evidence decision, produced by
a trusted controller using GitHub metadata and authenticated artifacts.
"""
from scripts.pr_merge_readiness import assess as assess_readiness


def assess_candidate(pr, files, checks, *, protected=False,
                     evidence_decision=None):
    """Return a non-authorizing status for a proposed low-risk merge."""
    readiness, reason = assess_readiness(pr, files, checks, protected=protected)
    if readiness != "candidate":
        return "manual", "merge readiness blocked: " + reason
    # The evidence decision must come from an independently trusted controller,
    # not from a model response, PR body, comment, or user-controlled artifact.
    if evidence_decision != ("candidate", "trusted-controller-verified"):
        return "manual", "independent review evidence verification required"
    return "candidate", "read-only candidate; privileged revalidation required"
