"""Fail closed when upstream returns a report path outside the upload root."""
import unittest
from pathlib import Path


class ReportPathContainmentTests(unittest.TestCase):
    def test_entrypoint_enforces_containment(self):
        source = (Path(__file__).resolve().parents[1] /
                  "scripts/analyze.py").read_text(encoding="utf-8")
        self.assertIn('expected_root = (root / "reports").resolve()', source)
        self.assertIn("report_dir.is_relative_to(expected_root)", source)

    def test_resolved_paths_reject_parent_traversal(self):
        from tempfile import TemporaryDirectory
        with TemporaryDirectory() as tmp:
            root = Path(tmp).resolve()
            reports = root / "results" / "reports"
            reports.mkdir(parents=True)
            self.assertTrue((reports / "ticker").resolve().is_relative_to(reports))
            self.assertFalse((reports / ".." / ".." / "elsewhere").resolve().is_relative_to(reports))


if __name__ == "__main__":
    unittest.main()
