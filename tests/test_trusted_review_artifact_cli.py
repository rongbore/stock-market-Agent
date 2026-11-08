"""Offline CLI input/output contract tests."""
import hashlib
import io
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
import zipfile

from scripts.trusted_review_artifact_cli import evaluate_files

REPO = "rongbore/stock-market-Agent"
HEAD = "a" * 40
BASE = "b" * 40
WORKFLOW_PATH = ".github/workflows/ai-pr-review-manual.yml"
WORKFLOW_REF = REPO + "/" + WORKFLOW_PATH + "@refs/heads/main"
EVENT = "workflow_dispatch"


def evidence():
    return {"head_sha": HEAD, "base_sha": BASE, "artifact_sha": "c" * 40,
            "workflow_run_id": 123, "request_digest": "d" * 64,
            "repository": REPO, "workflow_path": WORKFLOW_PATH,
            "workflow_ref": WORKFLOW_REF, "workflow_sha": "e" * 40,
            "event": EVENT, "verdict": "approve", "findings": []}


def fixture_files(directory):
    archive_path = Path(directory) / "artifact.zip"
    stream = io.BytesIO()
    with zipfile.ZipFile(stream, "w", zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("ai-review-evidence.json", json.dumps(evidence()))
    archive_bytes = stream.getvalue()
    archive_path.write_bytes(archive_bytes)
    metadata = {
        "repo": REPO, "current_head_sha": HEAD, "current_base_sha": BASE,
        "expected_request_digest": "d" * 64, "expected_workflow_id": 77,
        "expected_workflow_path": WORKFLOW_PATH, "expected_event": EVENT,
        "trusted_artifact_sha": "c" * 40, "trusted_workflow_ref": WORKFLOW_REF,
        "trusted_workflow_sha": "e" * 40,
        "run": {"repository_full_name": REPO, "head_repository_full_name": REPO,
                "head_sha": HEAD, "workflow_id": 77, "path": WORKFLOW_PATH,
                "event": EVENT, "status": "completed", "conclusion": "success",
                "id": 123, "run_attempt": 1},
        "artifact": {"workflow_run_id": 123, "id": 456, "expired": False,
                     "size_in_bytes": len(archive_bytes), "name": "ai-review-evidence",
                     "digest": "sha256:" + hashlib.sha256(archive_bytes).hexdigest()},
    }
    metadata_path = Path(directory) / "metadata.json"
    metadata_path.write_text(json.dumps(metadata), encoding="utf-8")
    return metadata_path, archive_path, metadata


class TrustedReviewArtifactCliTests(unittest.TestCase):
    def test_valid_inputs_emit_non_authorizing_summary(self):
        with tempfile.TemporaryDirectory() as directory:
            metadata, archive, _ = fixture_files(directory)
            result = evaluate_files(metadata, archive)
        self.assertEqual(result["status"], "candidate")
        self.assertTrue(result["evidence_authenticated"])
        self.assertFalse(result["merge_authorized"])
        self.assertNotIn("evidence", result)

    def test_bad_metadata_and_oversized_input_fail_closed(self):
        with tempfile.TemporaryDirectory() as directory:
            metadata_path, archive_path, metadata = fixture_files(directory)
            metadata["unexpected"] = "ignored input must not be accepted"
            metadata_path.write_text(json.dumps(metadata), encoding="utf-8")
            with self.assertRaises(ValueError):
                evaluate_files(metadata_path, archive_path)
            metadata_path.write_text("{}", encoding="utf-8")
            archive_path.write_bytes(b"x" * (1024 * 1024 + 1))
            with self.assertRaises(ValueError):
                evaluate_files(metadata_path, archive_path)

    def test_module_entrypoint_emits_only_compact_advisory_result(self):
        repo_root = Path(__file__).resolve().parents[1]
        with tempfile.TemporaryDirectory() as directory:
            metadata_path, archive_path, _ = fixture_files(directory)
            command = [sys.executable, "-m", "scripts.trusted_review_artifact_cli",
                       "--metadata", str(metadata_path), "--archive", str(archive_path)]
            result = subprocess.run(command, cwd=repo_root, capture_output=True,
                                    text=True, timeout=10, check=False)
        self.assertEqual(result.returncode, 0)
        report = json.loads(result.stdout)
        self.assertEqual(report["status"], "candidate")
        self.assertFalse(report["merge_authorized"])
        self.assertNotIn("evidence", report)
        self.assertNotIn("request_digest", result.stdout)

    def test_module_entrypoint_reports_bad_inputs_without_details(self):
        repo_root = Path(__file__).resolve().parents[1]
        with tempfile.TemporaryDirectory() as directory:
            metadata_path, archive_path, _ = fixture_files(directory)
            metadata_path.write_text("{}", encoding="utf-8")
            command = [sys.executable, "-m", "scripts.trusted_review_artifact_cli",
                       "--metadata", str(metadata_path), "--archive", str(archive_path)]
            result = subprocess.run(command, cwd=repo_root, capture_output=True,
                                    text=True, timeout=10, check=False)
        self.assertEqual(result.returncode, 1)
        report = json.loads(result.stdout)
        self.assertEqual(report["status"], "manual")
        self.assertFalse(report["evidence_authenticated"])
        self.assertFalse(report["merge_authorized"])
        self.assertNotIn("request_digest", result.stdout)


if __name__ == "__main__":
    unittest.main()
