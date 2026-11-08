"""Verify and safely parse the single-file AI review evidence artifact.

This is offline validation only. It does not authenticate GitHub metadata,
submit reviews, invoke a model, or authorize merges.
"""
import hashlib
import hmac
import io
import json
import re
import stat
import zipfile

_DIGEST = re.compile(r"^sha256:[0-9a-f]{64}$")
_SHA = re.compile(r"^[0-9a-f]{40}$")
_REQUEST_DIGEST = re.compile(r"^[0-9a-f]{64}$")
_REPOSITORY = re.compile(r"^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+$")
_WORKFLOW_PATH = re.compile(r"^\.github/workflows/[A-Za-z0-9_.-]+\.ya?ml$")
_EXPECTED_KEYS = frozenset({
    "pr_number", "head_sha", "base_sha", "artifact_sha", "workflow_run_id",
    "request_digest", "repository", "workflow_path", "workflow_ref",
    "workflow_sha", "event", "verdict", "findings",
})
_MAX_ARCHIVE_BYTES = 1024 * 1024
_MAX_EVIDENCE_BYTES = 256 * 1024
_MAX_COMPRESSION_RATIO = 100


def _unique_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("duplicate JSON key")
        result[key] = value
    return result


def _valid_evidence(value):
    if not isinstance(value, dict) or set(value) != _EXPECTED_KEYS:
        raise ValueError("invalid evidence schema")
    if type(value["pr_number"]) is not int or value["pr_number"] <= 0:
        raise ValueError("invalid pull request number")
    for key in ("head_sha", "base_sha", "artifact_sha", "workflow_sha"):
        if not isinstance(value[key], str) or not _SHA.fullmatch(value[key]):
            raise ValueError("invalid evidence SHA")
    if type(value["workflow_run_id"]) is not int or value["workflow_run_id"] <= 0:
        raise ValueError("invalid workflow run ID")
    if not isinstance(value["request_digest"], str) or not _REQUEST_DIGEST.fullmatch(value["request_digest"]):
        raise ValueError("invalid request digest")
    if not isinstance(value["repository"], str) or not _REPOSITORY.fullmatch(value["repository"]):
        raise ValueError("invalid repository")
    if not isinstance(value["workflow_path"], str) or not _WORKFLOW_PATH.fullmatch(value["workflow_path"]):
        raise ValueError("invalid workflow path")
    if (not isinstance(value["workflow_ref"], str) or not value["workflow_ref"].strip()
            or len(value["workflow_ref"]) > 512):
        raise ValueError("invalid workflow ref")
    if value["event"] not in ("pull_request", "workflow_dispatch"):
        raise ValueError("invalid workflow event")
    if value["verdict"] not in ("approve", "request_changes", "uncertain"):
        raise ValueError("invalid verdict")
    findings = value["findings"]
    if not isinstance(findings, list) or len(findings) > 30:
        raise ValueError("invalid findings")
    for finding in findings:
        if not isinstance(finding, dict) or set(finding) != {"severity", "path", "explanation"}:
            raise ValueError("invalid finding")
        if finding["severity"] not in ("low", "medium", "high", "critical"):
            raise ValueError("invalid finding severity")
        if (not isinstance(finding["path"], str) or len(finding["path"]) > 250
                or not isinstance(finding["explanation"], str)
                or not finding["explanation"].strip() or len(finding["explanation"]) > 4000):
            raise ValueError("invalid finding fields")
        if "\x00" in finding["path"]:
            raise ValueError("invalid finding path")
    if value["verdict"] == "approve" and any(
            f["severity"] in ("high", "critical") for f in findings):
        raise ValueError("approval conflicts with severe finding")
    return value


def verify_review_artifact_archive(archive_bytes, expected_archive_digest):
    """Return validated evidence after digest and strict ZIP/JSON checks.

    The expected digest must come from authenticated GitHub artifact metadata;
    the caller remains responsible for verifying that metadata and PR context.
    """
    if not isinstance(archive_bytes, bytes) or not 0 < len(archive_bytes) <= _MAX_ARCHIVE_BYTES:
        raise ValueError("invalid or oversized artifact archive")
    if not isinstance(expected_archive_digest, str) or not _DIGEST.fullmatch(expected_archive_digest):
        raise ValueError("invalid expected artifact digest")
    actual_digest = "sha256:" + hashlib.sha256(archive_bytes).hexdigest()
    if not hmac.compare_digest(actual_digest, expected_archive_digest):
        raise ValueError("artifact archive digest mismatch")
    try:
        with zipfile.ZipFile(io.BytesIO(archive_bytes), "r") as archive:
            members = archive.infolist()
            if len(members) != 1:
                raise ValueError("artifact must contain exactly one file")
            member = members[0]
            if member.filename != "ai-review-evidence.json" or member.is_dir():
                raise ValueError("unexpected artifact member")
            mode = member.external_attr >> 16
            if stat.S_ISLNK(mode):
                raise ValueError("symbolic links are not allowed")
            if member.flag_bits & 0x1:
                raise ValueError("encrypted artifact member")
            if member.compress_type not in (zipfile.ZIP_STORED, zipfile.ZIP_DEFLATED):
                raise ValueError("unsupported artifact compression")
            if not 0 < member.file_size <= _MAX_EVIDENCE_BYTES:
                raise ValueError("invalid or oversized evidence file")
            if member.compress_size <= 0 or member.file_size > member.compress_size * _MAX_COMPRESSION_RATIO:
                raise ValueError("artifact compression ratio exceeded")
            with archive.open(member, "r") as source:
                raw = source.read(_MAX_EVIDENCE_BYTES + 1)
            if len(raw) != member.file_size or len(raw) > _MAX_EVIDENCE_BYTES:
                raise ValueError("evidence size mismatch")
    except (zipfile.BadZipFile, EOFError, OSError, RuntimeError, ValueError) as exc:
        if isinstance(exc, ValueError):
            raise
        raise ValueError("invalid artifact archive") from exc
    try:
        evidence = json.loads(raw.decode("utf-8"), object_pairs_hook=_unique_object)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ValueError("invalid evidence JSON") from exc
    return {"status": "candidate", "evidence": _valid_evidence(evidence),
            "archive_digest": actual_digest, "merge_authorized": False}
