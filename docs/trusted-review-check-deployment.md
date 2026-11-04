# Trusted review check deployment (not yet enforced)

This pure policy module verifies complete file metadata, an exact head commit,
and independent reviewer approvals associated with that same commit.
The trusted-reviewer list **must** come from an independently verified GitHub
permission lookup, never from PR metadata or a user-editable file.

**Important:** This code is not yet a GitHub required check. Do not enable
auto-merge until a protected-base workflow performs read-only paginated
GitHub API retrieval, independently verifies reviewer permissions and the
head SHA, then publishes a required check from a trusted workflow context.

The current repository ruleset must be strengthened to require pull requests
and the trusted risk check; otherwise sensitive changes can bypass review.
Do not trust PR-head workflows as approval authority. No workflow should
write to the repository or merge a PR until these protections are verified.
