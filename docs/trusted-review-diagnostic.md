# Trusted review diagnostic (informational only)

The workflow uses `pull_request_target` and checks out the protected default
branch, **not PR-head code**. It has read-only token permissions and makes no
merge or repository-write API calls.

It retrieves all changed-file and review pages and asks GitHub for reviewer
collaborator permissions. Permission lookup errors are not trusted. Missing
or malformed metadata is fail-closed in the policy decision.

**This workflow is deliberately not an enforcement gate.** Its job exits zero
even when the diagnostic says `eligible: false`, and it must NOT be added
to required checks. A production gate needs review-event correctness,
reviewer permission verification, head SHA race protection, and a required
check protected against untrusted workflow spoofing. The repository Ruleset
currently lacks the pull-request requirement. Configure and verify that
protection before enabling any auto-merger.
