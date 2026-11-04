import hashlib
import json
import tempfile
import unittest
from pathlib import Path
from scripts.disclosure_pdf_fingerprint import fingerprint, main


class DisclosureFingerprintTests(unittest.TestCase):
    def test_offline_pdf_fingerprint_and_cli(self):
        with tempfile.TemporaryDirectory() as tmp:
            folder = Path(tmp)
            pdf = folder / "sample.pdf"
            content = b"%PDF-1.4\nsynthetic test bytes\n%%EOF\n"
            pdf.write_bytes(content)
            result = fingerprint(pdf, "000776.SZ", "2026-10-20")
            self.assertEqual(result["file_sha256"], hashlib.sha256(content).hexdigest())
            self.assertFalse(result["official_origin_verified"])
            self.assertFalse(result["source_content_verified"])
            output = folder / "evidence.json"
            self.assertEqual(main(["--pdf", str(pdf), "--symbol", "000776.SZ",
                                   "--announcement-date", "2026-10-20",
                                   "--output", str(output)]), 0)
            self.assertEqual(json.loads(output.read_text())["file_size_bytes"], len(content))

    def test_reject_non_pdf(self):
        with tempfile.TemporaryDirectory() as tmp:
            file = Path(tmp) / "bad.pdf"
            file.write_bytes(b"not a PDF file")
            with self.assertRaisesRegex(ValueError, "PDF header"):
                fingerprint(file, "000776.SZ", "2026-10-20")

    def test_reject_invalid_symbol_or_date(self):
        with tempfile.TemporaryDirectory() as tmp:
            file = Path(tmp) / "test.pdf"
            file.write_bytes(b"%PDF-1.4\n%%EOF")
            with self.assertRaises(ValueError):
                fingerprint(file, "000776.SZ;bad", "2026-10-20")
            with self.assertRaises(ValueError):
                fingerprint(file, "000776.SZ", "2026-02-30")

    def test_reject_oversized_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            file = Path(tmp) / "huge.pdf"
            with file.open("wb") as stream:
                stream.write(b"%PDF-1.4")
                stream.truncate(20 * 1024 * 1024 + 1)
            with self.assertRaisesRegex(ValueError, "size"):
                fingerprint(file, "000776.SZ", "2026-10-20")


if __name__ == "__main__":
    unittest.main()
