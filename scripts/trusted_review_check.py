"""Fail-closed review decision using GitHub review commit IDs and verified permissions.

This module does not grant merge permissions and does not access the network.
"""
from datetime import datetime

from scripts.pr_risk_classifier import classify


def check(pr, files, reviews, trusted_reviewers):
    if not isinstance(pr, dict) or not isinstance(files, list) or not isinstance(reviews, list):
        return False, "invalid pull request metadata"
    count = pr.get("changed_files")
    sha = pr.get("head_sha")
    author = pr.get("author")
    if type(count) is not int or count < 1 or count != len(files):
        return False, "incomplete changed-file listing"
    if not isinstance(sha, str) or len(sha) != 40 or any(c not in "0123456789abcdef" for c in sha):
        return False, "invalid head commit"
    if not isinstance(author, str) or not author:
        return False, "invalid author"
    if not isinstance(trusted_reviewers, (list, set, tuple)):
        return False, "unverified reviewer permissions"
    decision, reason = classify(files, expected_count=count)
    if decision == "eligible":
        return True, "low-risk documentation"
    latest = {}
    for review in reviews:
        if not isinstance(review, dict):
            return False, "malformed review"
        user, state, submitted = review.get("user"), review.get("state"), review.get("submitted_at")
        if not isinstance(user, str) or not isinstance(state, str) or not isinstance(submitted, str):
            return False, "malformed review metadata"
        if user not in latest or submitted > latest[user]["submitted_at"]:
            latest[user] = review
    if any(r["state"] == "CHANGES_REQUESTED" for _, r in latest.values()):
        return False, "unresolved change request"
    for user, (_, review) in latest.items():
        if (user != author and user in trusted_reviewers
                and review["state"] == "APPROVED" and review.get("commit_id") == sha):
            return True, "trusted independent approval for current head"
    return False, "manual approval on current head required: " + reason
