"""Real-parser coverage with a synthetic Chinese table; no official filing claim."""
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest

from scripts.financial_table_review_package import main


def synthetic_table_pdf(rows=None):
    rows = rows if rows is not None else [("", "本报告期", "年初至报告期末"),
            ("营业总收入（元）", "10.00", "30.00"),
            ("经营活动产生的现金流量净额（元）", "-", "-8,137.59")]
    commands = ["0.5 w"]
    for x in (20, 270, 400, 550):
        commands.append(f"{x} 610 m {x} 700 l S")
    for y in (610, 640, 670, 700):
        commands.append(f"20 {y} m 550 {y} l S")
    for row, texts in enumerate(rows):
        for x, text in zip((25, 275, 405), texts):
            if text:
                encoded = text.encode("utf-16-be").hex()
                commands.append(f"BT /F1 7 Tf {x} {680 - row*30} Td <{encoded}> Tj ET")
    stream = ("\n".join(commands) + "\n").encode("ascii")
    chars = sorted(set("".join("".join(row) for row in rows)))
    mapping = "\n".join(f"<{ord(c):04x}> <{ord(c):04x}>" for c in chars)
    cmap = ("/CIDInit /ProcSet findresource begin 12 dict begin begincmap\n"
            "/CIDSystemInfo << /Registry (Adobe) /Ordering (UCS) /Supplement 0 >> def\n"
            "/CMapName /Synthetic def /CMapType 2 def\n"
            "1 begincodespacerange <0000> <FFFF> endcodespacerange\n"
            f"{len(chars)} beginbfchar\n{mapping}\nendbfchar\n"
            "endcmap CMapName currentdict /CMap defineresource pop end end\n").encode("ascii")
    objects = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 600 800] /Resources << /Font << /F1 5 0 R >> >> /Contents 4 0 R >>",
        b"<< /Length " + str(len(stream)).encode() + b" >>\nstream\n" + stream + b"endstream",
        b"<< /Type /Font /Subtype /Type0 /BaseFont /STSong-Light /Encoding /Identity-H /DescendantFonts [6 0 R] /ToUnicode 7 0 R >>",
        b"<< /Type /Font /Subtype /CIDFontType0 /BaseFont /STSong-Light /CIDSystemInfo << /Registry (Adobe) /Ordering (GB1) /Supplement 4 >> /DW 1000 /FontDescriptor 8 0 R >>",
        b"<< /Length " + str(len(cmap)).encode() + b" >>\nstream\n" + cmap + b"endstream",
        b"<< /Type /FontDescriptor /FontName /STSong-Light /Flags 4 /FontBBox [0 -200 1000 900] /ItalicAngle 0 /Ascent 900 /Descent -200 /CapHeight 700 /StemV 80 >>",
    ]
    data = bytearray(b"%PDF-1.4\n")
    offsets = [0]
    for index, obj in enumerate(objects, 1):
        offsets.append(len(data))
        data.extend(f"{index} 0 obj\n".encode() + obj + b"\nendobj\n")
    xref = len(data)
    data.extend(f"xref\n0 {len(offsets)}\n0000000000 65535 f \n".encode())
    for offset in offsets[1:]:
        data.extend(f"{offset:010d} 00000 n \n".encode())
    data.extend((f"trailer\n<< /Size {len(offsets)} /Root 1 0 R >>\n"
                 f"startxref\n{xref}\n%%EOF\n").encode())
    return bytes(data)


@unittest.skipUnless(importlib.util.find_spec("pdfplumber"), "optional pdfplumber not installed")
class ReviewIntegrationTests(unittest.TestCase):
    def test_real_parser_table_to_cli_review_package(self):
        with tempfile.TemporaryDirectory() as folder:
            pdf, output = Path(folder) / "synthetic.pdf", Path(folder) / "review.json"
            pdf.write_bytes(synthetic_table_pdf())
            self.assertEqual(main(["--pdf", str(pdf), "--symbol", "000776.SZ",
                                   "--announcement-date", "2026-10-30", "--pages", "1",
                                   "--output", str(output)]), 0)
            result = json.loads(output.read_text())
        candidates = {c["cell"]["text"]: c for c in result["candidates"]}
        self.assertEqual(set(candidates), {"10.00", "30.00", "-8,137.59"})
        self.assertEqual(candidates["10.00"]["period_hint_unverified"], "current_quarter")
        self.assertEqual(candidates["30.00"]["period_hint_unverified"], "year_to_date")
        cash = candidates["-8,137.59"]
        self.assertEqual(cash["metric_hint_unverified"], "operating_cash_flow")
        self.assertEqual(cash["unit_hint_unverified"], "CNY")
        self.assertEqual(cash["period_hint_unverified"], "year_to_date")
        self.assertEqual(cash["cell"]["column_index"], 2)
        self.assertIn("consolidation_scope", cash["review_blockers"])
        self.assertEqual(result["status"], "PENDING_MANUAL_VERIFICATION")
        self.assertFalse(result["source_content_verified"])

    def test_table_with_only_placeholders_reports_no_numeric_evidence(self):
        with tempfile.TemporaryDirectory() as folder:
            pdf, output = Path(folder) / "empty.pdf", Path(folder) / "review.json"
            pdf.write_bytes(synthetic_table_pdf([
                ("", "本报告期", "年初至报告期末"),
                ("营业总收入（元）", "-", "-"),
                ("总资产（元）", "-", "-"),
            ]))
            main(["--pdf", str(pdf), "--symbol", "000776.SZ", "--announcement-date",
                  "2026-10-30", "--pages", "1", "--output", str(output)])
            result = json.loads(output.read_text())
        self.assertEqual(result["candidate_count"], 0)
        self.assertIn("no_numeric_candidates", result["review_blockers"])
        self.assertFalse(result["source_content_verified"])
