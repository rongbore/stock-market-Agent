import tempfile
import unittest
from pathlib import Path

from scripts.report_archive import archive_report


class ArchiveTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.base = Path(self.temp.name)
        self.source = self.base / "report"
        self.source.mkdir()
        (self.source / "report.md").write_text("synthetic report", encoding="utf-8")
        self.root = self.base / "archives"

    def archive(self):
        return archive_report(self.source, self.root, "000776.SZ", "2026-11-04")

    def test_archive_and_deduplicate(self):
        first, created = self.archive()
        self.assertTrue(created)
        self.assertEqual((first / "report.md").read_text(), "synthetic report")
        second, created = self.archive()
        self.assertEqual(first, second)
        self.assertFalse(created)

    def test_changed_report_gets_new_archive(self):
        first, _ = self.archive()
        (self.source / "report.md").write_text("updated synthetic report")
        second, _ = self.archive()
        self.assertNotEqual(first, second)
        self.assertTrue(first.exists())

    def test_tampered_archive_rejected(self):
        first, _ = self.archive()
        (first / "report.md").write_text("tampered")
        with self.assertRaises(ValueError):
            self.archive()

    def test_reject_overlap_and_bad_ticker(self):
        with self.assertRaises(ValueError):
            archive_report(self.source, self.source / "archive", "000776.SZ", "2026-11-04")
        with self.assertRaises(ValueError):
            archive_report(self.source, self.root, "../secret", "2026-11-04")

    def test_reject_symlink(self):
        (self.source / "link").symlink_to(self.source / "report.md")
        with self.assertRaises(ValueError):
            self.archive()


if __name__ == "__main__":
    unittest.main()
