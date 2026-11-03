import tempfile
import unittest
from pathlib import Path

from scripts.artifact_secret_guard import validate_artifact_secrets


class ArtifactSecretGuardTests(unittest.TestCase):
    def test_clean_html_passes(self):
        with tempfile.TemporaryDirectory() as tmp:
            (Path(tmp) / "complete_report.html").write_text("<html>clean</html>")
            self.assertEqual(validate_artifact_secrets(tmp, secrets=["synthetic-key-123"]), [])

    def test_detects_secret_without_echoing_it(self):
        secret = "synthetic-key-123"
        with tempfile.TemporaryDirectory() as tmp:
            (Path(tmp) / "complete_report.html").write_text("<html>" + secret + "</html>")
            errors = validate_artifact_secrets(tmp, secrets=[secret])
            self.assertTrue(errors)
            self.assertNotIn(secret, str(errors))

    def test_detects_json_leak(self):
        with tempfile.TemporaryDirectory() as tmp:
            (Path(tmp) / "run_provenance.json").write_text('{"token":"synthetic-key-123"}')
            self.assertTrue(validate_artifact_secrets(tmp, secrets=["synthetic-key-123"]))

    def test_rejects_symlinks(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "target.txt").write_text("clean")
            (root / "linked.txt").symlink_to(root / "target.txt")
            self.assertTrue(validate_artifact_secrets(root, secrets=[]))

    def test_rejects_missing_directory(self):
        with tempfile.TemporaryDirectory() as tmp:
            self.assertTrue(validate_artifact_secrets(Path(tmp) / "absent", secrets=[]))

    def test_workflow_guard_precedes_upload(self):
        workflow = (Path(__file__).resolve().parents[1] /
                    ".github/workflows/analyze.yml").read_text(encoding="utf-8")
        self.assertLess(workflow.index("      - name: Validate report artifacts"),
                        workflow.index("      - name: Guard report artifacts"))
        self.assertLess(workflow.index("      - name: Guard report artifacts"),
                        workflow.index("      - name: Upload reports"))


if __name__ == "__main__":
    unittest.main()
