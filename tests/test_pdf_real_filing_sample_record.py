import hashlib
import tempfile
import unittest
from pathlib import Path

from scripts.pdf_real_filing_sample_record import make_sample_record, main


SOURCE = "https://static.cninfo.com.cn/finalpage/2026-03-31/1225060422.PDF"


class RealFilingSampleRecordTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.pdf = Path(self.temp.name) / "report.pdf"
        self.pdf.write_bytes(b"%PDF-1.4\nsynthetic fixture\n%%EOF")

    def record(self, url=SOURCE):
        return make_sample_record(self.pdf, "000776.SZ", "2026-03-31", url)

    def test_records_local_hash_but_never_claims_source_match(self):
        result = self.record()
        self.assertEqual(result["file_sha256"], hashlib.sha256(self.pdf.read_bytes()).hexdigest())
        self.assertEqual(result["source_url_claimed"], SOURCE)
        self.assertFalse(result["source_file_match_verified"])
        self.assertFalse(result["official_origin_verified"])
        self.assertFalse(result["financial_meaning_verified"])

    def test_rejects_untrusted_domain(self):
        with self.assertRaisesRegex(ValueError, "hostname"):
            self.record("https://example.com/report.pdf")

    def test_rejects_http_and_url_credentials(self):
        for url in ("http://static.cninfo.com.cn/file.pdf",
                    "https://user:pass@static.cninfo.com.cn/file.pdf"):
            with self.subTest(url=url), self.assertRaises(ValueError):
                self.record(url)

    def test_cli_rejects_overwriting_pdf(self):
        with self.assertRaisesRegex(ValueError, "overwrite"):
            main(["--pdf", str(self.pdf), "--symbol", "000776.SZ",
                  "--announcement-date", "2026-03-31",
                  "--source-url", SOURCE, "--output", str(self.pdf)])


if __name__ == "__main__":
    unittest.main()
