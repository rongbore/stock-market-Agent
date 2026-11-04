import json
import tempfile
import unittest
from pathlib import Path

from scripts.pdf_sample_bundle_cli import build_sample_bundle, main
from test_offline_pdf_rectangle_integration import make_pdf_with_rectangle


SOURCE = "https://static.cninfo.com.cn/finalpage/2026-03-31/1225060422.PDF"


class PdfSampleBundleCliTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.pdf = Path(self.temp.name) / "synthetic.pdf"
        self.pdf.write_bytes(make_pdf_with_rectangle())
        self.output = Path(self.temp.name) / "bundle.json"

    def args(self):
        return ["--pdf", str(self.pdf), "--symbol", "000776.SZ",
                "--announcement-date", "2026-03-31",
                "--source-url", SOURCE, "--pages", "1",
                "--output", str(self.output)]

    def test_real_pdfplumber_bundle_has_consistent_sha_and_unverified_flags(self):
        self.assertEqual(main(self.args()), 0)
        bundle = json.loads(self.output.read_text(encoding="utf-8"))
        self.assertEqual(bundle["source_record"]["file_sha256"],
                         bundle["review_manifest"]["file_sha256"])
        self.assertEqual(bundle["review_manifest"]["candidate_count"], 1)
        self.assertEqual(bundle["review_manifest"]["candidates"][0]["bbox"],
                         [20, 120, 240, 220])
        self.assertTrue(bundle["sample_checked_with_real_pdf_parser"])
        self.assertFalse(bundle["official_origin_verified"])
        self.assertFalse(bundle["financial_meaning_verified"])

    def test_rejects_page_out_of_range_without_output(self):
        args = self.args()
        args[args.index("--pages") + 1] = "2"
        with self.assertRaisesRegex(ValueError, "out of range"):
            main(args)
        self.assertFalse(self.output.exists())

    def test_rejects_overwriting_pdf(self):
        args = self.args()
        args[-1] = str(self.pdf)
        with self.assertRaisesRegex(ValueError, "overwrite"):
            main(args)


if __name__ == "__main__":
    unittest.main()
