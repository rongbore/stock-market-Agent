import copy
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from scripts.financial_table_package_validation import validate_table_review_package, main
from scripts.financial_table_review_package import build_review_package
from tests.test_financial_table_review_integration import synthetic_table_pdf


def package():
    def cell(text, row, col, x0, x1):
        return dict(page=1, table_index=0, row_index=row, column_index=col, text=text,
                    bbox=[x0, row * 20, x1, row * 20 + 10])
    cells = [cell("年初至报告期末", 0, 1, 50, 100),
             cell("营业总收入（元）", 1, 0, 0, 45), cell("10.00", 1, 1, 60, 90)]
    with patch("scripts.financial_table_review_package._pdf_digest", return_value="a" * 64), patch(
            "scripts.financial_table_review_package.extract_table_cells",
            return_value={"file_sha256": "a" * 64, "cells": cells}):
        return build_review_package("fixture.pdf", "000776.SZ", "2026-10-30", [1])


class PackageValidationTests(unittest.TestCase):
    def test_valid_package_structure_is_not_release_evidence(self):
        p = package()
        original = copy.deepcopy(p)
        result = validate_table_review_package(p)
        self.assertTrue(result["structure_valid"])
        self.assertFalse(result["release_evidence_accepted"])
        self.assertFalse(result["financial_meaning_verified"])
        self.assertEqual(p, original)

    def test_missing_false_flags_and_removed_blockers_rejected(self):
        for edit in (lambda p: p.pop("source_content_verified"),
                     lambda p: p.update(official_origin_verified=True),
                     lambda p: p.update(review_blockers=[]),
                     lambda p: p["candidates"][0].update(review_blockers=[])):
            p = package()
            edit(p)
            with self.assertRaises(ValueError):
                validate_table_review_package(p)

    def test_absent_hints_and_empty_evidence_keep_required_blockers(self):
        p = package()
        c = p["candidates"][0]
        c.update(header_cell=None, period_hint_unverified=None, reason="missing_or_ambiguous_header",
                 metric_hint_unverified=None, unit_hint_unverified=None, label_cells=[],
                 metric_reason="missing_or_ambiguous_row_label",
                 review_blockers=["metric", "unit", "period", "consolidation_scope", "manual_verification"])
        self.assertTrue(validate_table_review_package(p)["structure_valid"])
        p.update(candidates=[], candidate_count=0,
                 review_blockers=["no_numeric_candidates", "consolidation_scope", "manual_verification"])
        result = validate_table_review_package(p)
        self.assertEqual(result["candidate_count"], 0)
        self.assertFalse(result["release_evidence_accepted"])

    def test_wrong_period_or_cross_table_header_rejected(self):
        for edit in (lambda c: c.update(period_hint_unverified="current_quarter"),
                     lambda c: c["header_cell"].update(table_index=1),
                     lambda c: c["header_cell"].update(bbox=[0, 0, 10, 10])):
            p = package()
            edit(p["candidates"][0])
            with self.assertRaises(ValueError):
                validate_table_review_package(p)

    def test_wrong_metric_unit_or_label_geometry_rejected(self):
        for edit in (lambda c: c.update(metric_hint_unverified="total_assets"),
                     lambda c: c.update(unit_hint_unverified="CNY_10000"),
                     lambda c: c["label_cells"][0].update(row_index=2),
                     lambda c: c["label_cells"][0].update(bbox=[70, 20, 100, 30])):
            p = package()
            edit(p["candidates"][0])
            with self.assertRaises(ValueError):
                validate_table_review_package(p)

    def test_duplicate_cells_unknown_scope_or_noncanonical_date_rejected(self):
        p = package()
        p["candidates"] *= 2
        p["candidate_count"] = 2
        with self.assertRaises(ValueError):
            validate_table_review_package(p)
        p = package()
        p["candidates"][0]["consolidation_scope"] = "consolidated"
        with self.assertRaises(ValueError):
            validate_table_review_package(p)
        p = package()
        p["announcement_date_supplied_unverified"] = "20261030"
        with self.assertRaises(ValueError):
            validate_table_review_package(p)

    def test_cli_preserves_previous_result_on_invalid_input(self):
        with tempfile.TemporaryDirectory() as folder:
            source, output = Path(folder)/"package.json", Path(folder)/"validation.json"
            p = package()
            source.write_text(json.dumps(p))
            main(["--package", str(source), "--output", str(output)])
            original = output.read_bytes()
            p["review_blockers"] = []
            source.write_text(json.dumps(p))
            with self.assertRaises(ValueError):
                main(["--package", str(source), "--output", str(output)])
            self.assertEqual(output.read_bytes(), original)

    @unittest.skipUnless(importlib.util.find_spec("pdfplumber"), "optional pdfplumber not installed")
    def test_real_parser_generated_package_passes_structure_checks(self):
        with tempfile.TemporaryDirectory() as folder:
            pdf = Path(folder)/"synthetic.pdf"
            pdf.write_bytes(synthetic_table_pdf())
            p = build_review_package(pdf, "000776.SZ", "2026-10-30", [1])
        self.assertEqual(validate_table_review_package(p)["candidate_count"], 3)
