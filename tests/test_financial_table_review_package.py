import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from scripts.financial_filing_evidence_bundle import _pdf_digest
from scripts.financial_table_review_package import build_review_package, main


class ReviewPackageTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.pdf = Path(self.tmp.name) / "filing.pdf"
        self.pdf.write_bytes(b"%PDF-1.4\nfixture\n%%EOF\n")
        def cell(text, row, col, x0, x1):
            return dict(page=1, table_index=0, row_index=row, column_index=col,
                        text=text, bbox=[x0, row*20, x1, row*20+10])
        self.extracted = {"file_sha256": _pdf_digest(self.pdf), "cells": [
            cell("年初至报告期末", 0, 1, 50, 100),
            cell("营业总收入（元）", 1, 0, 0, 45), cell("1,000.00", 1, 1, 60, 90),
            cell("2", 2, 1, 60, 90)]}

    def test_cli_preserves_evidence_and_unresolved_scope(self):
        output = Path(self.tmp.name) / "review.json"
        with patch("scripts.financial_table_review_package.extract_table_cells", return_value=self.extracted):
            main(["--pdf", str(self.pdf), "--symbol", "000776.SZ",
                  "--announcement-date", "2026-10-30", "--pages", "1", "--output", str(output)])
        result = json.loads(output.read_text())
        first, missing = result["candidates"]
        self.assertEqual(first["metric_hint_unverified"], "revenue")
        self.assertEqual(first["cell"]["text"], "1,000.00")
        self.assertEqual(first["review_blockers"], ["consolidation_scope", "manual_verification"])
        self.assertIn("metric", missing["review_blockers"])
        self.assertFalse(result["financial_meaning_verified"])
        self.assertEqual(result["status"], "PENDING_MANUAL_VERIFICATION")

    def test_rejects_extraction_hash_mismatch(self):
        self.extracted["file_sha256"] = "0" * 64
        with patch("scripts.financial_table_review_package.extract_table_cells", return_value=self.extracted):
            with self.assertRaisesRegex(ValueError, "changed"):
                build_review_package(self.pdf, "000776.SZ", "2026-10-30", [1])

    def test_cli_cannot_overwrite_pdf(self):
        original = self.pdf.read_bytes()
        with self.assertRaisesRegex(ValueError, "overwrite"):
            main(["--pdf", str(self.pdf), "--symbol", "000776.SZ", "--announcement-date",
                  "2026-10-30", "--pages", "1", "--output", str(self.pdf)])
        self.assertEqual(self.pdf.read_bytes(), original)
