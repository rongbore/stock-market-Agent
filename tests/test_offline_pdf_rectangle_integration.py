import tempfile
import unittest
from pathlib import Path

from scripts.offline_pdf_rectangle_extract import extract_rectangle_candidates


def make_pdf_with_rectangle():
    """Create a valid one-page PDF containing a 220 x 100 pt stroked rectangle."""
    stream = b"20 80 220 100 re S\n"
    objects = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 300 300] /Resources << >> /Contents 4 0 R >>",
        b"<< /Length " + str(len(stream)).encode("ascii") + b" >>\nstream\n" + stream + b"endstream",
    ]
    data = bytearray(b"%PDF-1.4\n")
    offsets = [0]
    for i, obj in enumerate(objects, 1):
        offsets.append(len(data))
        data.extend(f"{i} 0 obj\n".encode("ascii") + obj + b"\nendobj\n")
    xref = len(data)
    data.extend(f"xref\n0 {len(offsets)}\n0000000000 65535 f \n".encode("ascii"))
    for offset in offsets[1:]:
        data.extend(f"{offset:010d} 00000 n \n".encode("ascii"))
    data.extend((f"trailer\n<< /Size {len(offsets)} /Root 1 0 R >>\n"
                 f"startxref\n{xref}\n%%EOF\n").encode("ascii"))
    return bytes(data)


class RealPdfRectangleIntegrationTests(unittest.TestCase):
    def test_real_pdfplumber_reads_drawn_rectangle(self):
        try:
            import pdfplumber  # noqa: F401
        except ImportError:
            self.skipTest("optional pdfplumber is not installed")
        with tempfile.TemporaryDirectory() as folder:
            pdf = Path(folder) / "rectangle.pdf"
            pdf.write_bytes(make_pdf_with_rectangle())
            result = extract_rectangle_candidates(pdf, "000776.SZ", "2026-10-20", [1])
        self.assertEqual(len(result["regions"]), 1)
        self.assertEqual(result["regions"][0]["bbox"], [20, 120, 240, 220])
        self.assertFalse(result["table_boundaries_verified"])
        self.assertFalse(result["official_origin_verified"])


if __name__ == "__main__":
    unittest.main()
