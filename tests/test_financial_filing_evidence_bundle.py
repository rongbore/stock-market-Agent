import hashlib
import tempfile
import unittest
from pathlib import Path

from scripts.financial_filing_evidence_bundle import build_filing_evidence_bundle


CONTENT = b"%PDF-1.4\nsynthetic test filing\n%%EOF\n"
DIGEST = hashlib.sha256(CONTENT).hexdigest()


def source(**changes):
    row = {
        "symbol": "000776.SZ", "provider": "CNINFO", "title": "2026年第三季度报告",
        "source_url": "https://static.cninfo.com.cn/finalpage/sample.pdf",
        "published_at": "2026-10-29T16:00:00+08:00",
        "retrieved_at": "2026-10-30T10:00:00+08:00", "sha256": DIGEST,
    }
    row.update(changes)
    return row


def claim(**changes):
    row = {
        "symbol": "000776.SZ", "metric": "revenue", "metric_label": "营业总收入",
        "value": "37055611760.37", "unit": "CNY",
        "period_basis": "year_to_date", "period_start": "2026-01-01",
        "period_end": "2026-09-30", "consolidation_scope": "consolidated",
        "source_sha256": DIGEST, "page": 1,
        "excerpt": "营业总收入 年初至报告期末 37,055,611,760.37元",
    }
    row.update(changes)
    return row


class FinancialFilingEvidenceBundleTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.pdf = Path(self.tmp.name) / "filing.pdf"
        self.pdf.write_bytes(CONTENT)

    def tearDown(self):
        self.tmp.cleanup()

    def build(self, source_row=None, claim_row=None, cutoff="2026-10-31T23:59:59+08:00"):
        return build_filing_evidence_bundle(
            pdf_path=self.pdf, source=source_row or source(), claims=[claim_row or claim()],
            symbol="000776.SZ", analysis_cutoff=cutoff,
        )

    def test_end_to_end_bundle_preserves_unverified_boundaries(self):
        result = self.build()
        self.assertEqual(result["status"], "PENDING_MANUAL_VERIFICATION")
        self.assertEqual(result["source"]["sha256"], DIGEST)
        self.assertEqual(result["claims"][0]["period_basis"], "year_to_date")
        self.assertFalse(result["source_content_verified"])
        self.assertFalse(result["historical_point_in_time_verified"])
        self.assertFalse(result["claims"][0]["value_verified"])

    def test_rejects_modified_pdf_bytes(self):
        self.pdf.write_bytes(CONTENT + b"changed")
        with self.assertRaisesRegex(ValueError, "SHA-256"):
            self.build()

    def test_rejects_retrieval_after_cutoff(self):
        with self.assertRaisesRegex(ValueError, "retrieved after"):
            self.build(cutoff="2026-10-29T17:00:00+08:00")

    def test_rejects_naive_timestamp(self):
        with self.assertRaisesRegex(ValueError, "timezone"):
            self.build(source_row=source(published_at="2026-10-29T16:00:00"))

    def test_rejects_claim_after_disclosure_cutoff(self):
        with self.assertRaisesRegex(ValueError, "period is outside"):
            self.build(claim_row=claim(period_end="2026-12-31"))

    def test_rejects_inconsistent_metric_label_and_basis(self):
        with self.assertRaisesRegex(ValueError, "metric label"):
            self.build(claim_row=claim(metric_label="营业收入"))
        with self.assertRaisesRegex(ValueError, "only valid for total_assets"):
            self.build(claim_row=claim(period_basis="period_end", period_start=None))

    def test_rejects_non_ytd_start_and_quarter_mismatch(self):
        with self.assertRaisesRegex(ValueError, "January 1"):
            self.build(claim_row=claim(period_start="2026-01-02"))
        with self.assertRaisesRegex(ValueError, "one calendar quarter"):
            self.build(claim_row=claim(period_basis="current_quarter", period_start="2026-04-01"))

    def test_rejects_fake_verified_flag_and_duplicate_location(self):
        with self.assertRaisesRegex(ValueError, "verification claim"):
            self.build(claim_row=claim(value_verified=True))
        with self.assertRaisesRegex(ValueError, "duplicate"):
            build_filing_evidence_bundle(
                pdf_path=self.pdf, source=source(), claims=[claim(), claim()],
                symbol="000776.SZ", analysis_cutoff="2026-10-31T23:59:59+08:00",
            )

    def test_rejects_bad_symbol_and_untrusted_url_scheme(self):
        with self.assertRaisesRegex(ValueError, "source URL"):
            self.build(source_row=source(source_url="http://example.org/report.pdf"))


if __name__ == "__main__":
    unittest.main()
