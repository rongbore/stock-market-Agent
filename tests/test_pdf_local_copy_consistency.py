import tempfile
import unittest
from pathlib import Path

from scripts.pdf_local_copy_consistency import compare_local_pdf_copies, main


class LocalPdfCopyConsistencyTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.first = Path(self.temp.name) / "first.pdf"
        self.second = Path(self.temp.name) / "second.pdf"
        self.first.write_bytes(b"%PDF-1.4\nsynthetic fixture\n%%EOF")
        self.second.write_bytes(self.first.read_bytes())

    def test_equal_copies_do_not_prove_official_origin(self):
        result = compare_local_pdf_copies(self.first, self.second)
        self.assertTrue(result["byte_identical_by_sha256"])
        self.assertFalse(result["official_origin_verified"])
        self.assertFalse(result["financial_meaning_verified"])

    def test_different_copies(self):
        self.second.write_bytes(b"%PDF-1.4\ndifferent fixture\n%%EOF")
        self.assertFalse(compare_local_pdf_copies(self.first, self.second)["byte_identical_by_sha256"])

    def test_rejects_invalid_pdf_header(self):
        self.second.write_bytes(b"not a pdf")
        with self.assertRaisesRegex(ValueError, "header"):
            compare_local_pdf_copies(self.first, self.second)

    def test_rejects_missing_file(self):
        self.second.unlink()
        with self.assertRaisesRegex(ValueError, "not found"):
            compare_local_pdf_copies(self.first, self.second)

    def test_prevents_output_overwriting_pdf(self):
        with self.assertRaisesRegex(ValueError, "overwrite"):
            main(["--first", str(self.first), "--second", str(self.second),
                  "--output", str(self.first)])


if __name__ == "__main__":
    unittest.main()
