"""Fail-closed PR risk/approval decision; never performs a merge."""
from datetime import datetime

from scripts.pr_risk_classifier import classify


def evaluate(pr, files, reviews):
    if not isinstance(pr, dict) or not isinstance(files, list) or not isinstance(reviews, list):
        return False, "missing PR, file or review data"
    count = pr.get("changed_files")
    if type(count) is not int or count < 1 or count != len(files):
        return False, "incomplete or invalid changed-file listing"
    risk, reason = classify(files, expected_count=count)
    if risk == "eligible":
        return True, "low-risk documentation change"
    author = pr.get("user")
    pushed = pr.get("pushed_at")
    if not isinstance(author, str) or not isinstance(pushed, str):
        return False, "missing author or latest push timestamp"
    try:
        pushed_time = datetime.fromisoformat(pushed.replace("Z", "+00:00"))
        if pushed_time.tzinfo is None:
            return False, "push timestamp lacks timezone"
    except ValueError:
        return False, "invalid latest push timestamp"
    latest = {}
    for review in reviews:
        if not isinstance(review, dict):
            return False, "malformed review"
        user, state, submitted = review.get("user"), review.get("state"), review.get("submitted_at")
        if not isinstance(user, str) or not isinstance(state, str):
            return False, "malformed review identity"
        if state not in ("APPROVED", "CHANGES_REQUESTED", "COMMENTED", "DISMISSED"):
            continue
        if not isinstance(submitted, str):
            return False, "missing review timestamp"
        try:
            when = datetime.fromisoformat(submitted.replace("Z", "+00:00"))
            if when.tzinfo is None:
                return False, "review timestamp lacks timezone"
        except ValueError:
            return False, "invalid review timestamp"
        if user not in latest or when >= latest[user][0]:
            latest[user] = (when, state)
    if any(state == "CHANGES_REQUESTED" for _, state in latest.values()):
        return False, "outstanding changes-requested review"
    for user, (when, state) in latest.items():
        if user != author and state == "APPROVED" and when > pushed_time:
            return True, "sensitive change approved by another reviewer after last push"
    return False, "sensitive change requires independent approval after latest push: " + reason
