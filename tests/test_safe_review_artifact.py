"""Offline safety checks for downloaded AI review evidence archives."""
import hashlib
import io
import json
import zipfile
import unittest

from scripts.safe_review_artifact import verify_review_artifact_archive


def evidence():
    return {
        "pr_number": 321,
        "head_sha": "a" * 40,
        "base_sha": "b" * 40,
        "artifact_sha": "c" * 40,
        "workflow_run_id": 123,
        "request_digest": "d" * 64,
        "repository": "rongbore/stock-market-Agent",
        "workflow_path": ".github/workflows/ai-pr-review-manual.yml",
        "workflow_ref": "rongbore/stock-market-Agent/.github/workflows/ai-pr-review-manual.yml@refs/heads/main",
        "workflow_sha": "e" * 40,
        "event": "workflow_dispatch",
        "verdict": "approve",
        "findings": [],
    }


def archive(payload=None, filename="ai-review-evidence.json", extra=None):
    stream = io.BytesIO()
    with zipfile.ZipFile(stream, "w", zipfile.ZIP_DEFLATED) as bundle:
        bundle.writestr(filename, json.dumps(evidence() if payload is None else payload))
        if extra is not None:
            bundle.writestr("extra.txt", "not allowed")
    return stream.getvalue()


def digest(data):
    return "sha256:" + hashlib.sha256(data).hexdigest()


class SafeReviewArtifactTests(unittest.TestCase):
    def test_valid_archive_returns_advisory_evidence(self):
        raw = archive()
        result = verify_review_artifact_archive(raw, digest(raw))
        self.assertEqual(result["status"], "candidate")
        self.assertEqual(result["evidence"], evidence())
        self.assertFalse(result["merge_authorized"])

    def test_digest_mismatch_and_invalid_input_block(self):
        raw = archive()
        with self.assertRaises(ValueError):
            verify_review_artifact_archive(raw, "sha256:" + "0" * 64)
        for value in (b"", bytearray(raw), b"x" * (1024 * 1024 + 1)):
            with self.subTest(value_type=type(value).__name__):
                with self.assertRaises(ValueError):
                    verify_review_artifact_archive(value, digest(raw))

    def test_archive_must_have_one_expected_member(self):
        for raw in (archive(filename="../ai-review-evidence.json"),
                    archive(extra=True), b"not a zip"):
            with self.subTest(size=len(raw)):
                with self.assertRaises(ValueError):
                    verify_review_artifact_archive(raw, digest(raw))

    def test_invalid_schema_duplicate_json_keys_and_bad_verdict_block(self):
        invalid = evidence()
        invalid["unexpected"] = True
        raw = archive(invalid)
        with self.assertRaises(ValueError):
            verify_review_artifact_archive(raw, digest(raw))
        invalid = evidence()
        invalid["pr_number"] = True
        raw = archive(invalid)
        with self.assertRaises(ValueError):
            verify_review_artifact_archive(raw, digest(raw))
        duplicate_json = b'{"verdict":"approve","verdict":"uncertain"}'
        stream = io.BytesIO()
        with zipfile.ZipFile(stream, "w", zipfile.ZIP_DEFLATED) as bundle:
            bundle.writestr("ai-review-evidence.json", duplicate_json)
        raw = stream.getvalue()
        with self.assertRaises(ValueError):
            verify_review_artifact_archive(raw, digest(raw))
        invalid = evidence()
        invalid["verdict"] = "approve"
        invalid["findings"] = [{"severity": "critical", "path": "x.py", "explanation": "bad"}]
        raw = archive(invalid)
        with self.assertRaises(ValueError):
            verify_review_artifact_archive(raw, digest(raw))


if __name__ == "__main__":
    unittest.main()
