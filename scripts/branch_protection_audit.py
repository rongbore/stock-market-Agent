"""Conservative, read-only audit of GitHub branch-protection API data.

This helper does not call GitHub and cannot enable merging. A controller must
obtain trusted, current API responses and verify effective permissions.
"""

REQUIRED_CONTEXTS = frozenset({"unit-tests", "merge-policy"})


def audit_legacy_protection(data):
    if not isinstance(data, dict):
        return False, "protection response missing or inaccessible"
    checks = data.get("required_status_checks")
    if not isinstance(checks, dict) or checks.get("strict") is not True:
        return False, "strict required status checks not confirmed"
    contexts = checks.get("contexts")
    if not isinstance(contexts, list) or any(not isinstance(x, str) for x in contexts):
        return False, "required check contexts unavailable"
    if not REQUIRED_CONTEXTS.issubset(set(contexts)):
        return False, "required checks not configured"
    if not isinstance(data.get("enforce_admins"), dict) or data["enforce_admins"].get("enabled") is not True:
        return False, "administrator enforcement not confirmed"
    if not isinstance(data.get("allow_force_pushes"), dict) or data["allow_force_pushes"].get("enabled") is not False:
        return False, "force pushes not explicitly disabled"
    if not isinstance(data.get("allow_deletions"), dict) or data["allow_deletions"].get("enabled") is not False:
        return False, "branch deletion not explicitly disabled"
    if data.get("required_pull_request_reviews") is None:
        return False, "pull request review policy not confirmed"
    return False, "legacy fields alone cannot establish effective bypass-free protection"


def audit_repository_state(rulesets, legacy):
    if not isinstance(rulesets, list):
        return False, "ruleset API unavailable"
    if not rulesets:
        return False, "no repository rulesets; effective protection unverified"
    # Rule names and summary metadata are insufficient to prove effective
    # enforcement, bypass restrictions, required checks and reviews.
    return False, "ruleset details and effective enforcement require trusted audit"


if __name__ == "__main__":
    raise SystemExit("Read-only module: import audit_repository_state()")
