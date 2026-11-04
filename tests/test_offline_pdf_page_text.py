import tempfile
import unittest
from pathlib import Path
from scripts.offline_pdf_page_text import extract_pages


class FakePage:
    def __init__(self, text):
        self.text = text

    def extract_text(self):
        return self.text


class FakeReader:
    is_encrypted = False

    def __init__(self, stream):
        self.pages = [FakePage("营业收入 123.45"), FakePage("")]


class OfflinePdfPageTextTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.file = Path(self.tmp.name) / "local.pdf"
        self.file.write_bytes(b"%PDF-1.4\nsynthetic fixture\n%%EOF")

    def extract(self, pages, reader=FakeReader):
        return extract_pages(self.file, "000776.SZ", "2026-10-20", pages, reader)

    def test_page_text_and_empty_page_are_unverified(self):
        records = self.extract([1, 2])
        self.assertEqual(records[0]["text"], "营业收入 123.45")
        self.assertEqual(records[0]["text_extraction_status"], "text_extracted_unverified")
        self.assertEqual(records[1]["text_extraction_status"], "no_extractable_text")
        self.assertFalse(records[0]["financial_meaning_verified"])

    def test_reject_out_of_range_page(self):
        with self.assertRaisesRegex(ValueError, "out of range"):
            self.extract([3])

    def test_reject_duplicate_and_boolean_page(self):
        for pages in ([1, 1], [True], []):
            with self.subTest(pages=pages), self.assertRaises(ValueError):
                self.extract(pages)

    def test_reject_encrypted_pdf(self):
        class EncryptedReader(FakeReader):
            is_encrypted = True
        with self.assertRaisesRegex(ValueError, "encrypted"):
            self.extract([1], EncryptedReader)

    def test_reject_non_pdf_file(self):
        self.file.write_bytes(b"not a pdf")
        with self.assertRaisesRegex(ValueError, "PDF header"):
            self.extract([1])


if __name__ == "__main__":
    unittest.main()
