import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


class DisclosureCLIOfficialSourceTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.input = self.root / "notices.json"
        self.output = self.root / "output"
        self.record = {
            "symbol": "000776.SZ",
            "title": "SYNTHETIC ANNOUNCEMENT",
            "url": "https://static.cninfo.com.cn/finalpage/test.pdf",
            "announcement_date": "2026-10-29",
        }

    def run_cli(self):
        self.input.write_text(json.dumps([self.record]), encoding="utf-8")
        return subprocess.run(
            [sys.executable, "-m", "scripts.disclosure_candidates",
             str(self.input), "--analysis-date", "2026-10-30",
             "--symbol", "000776.SZ", "--output-dir", str(self.output),
             "--official-source", "cninfo"],
            capture_output=True, text=True, check=False,
        )

    def test_report_contract_direct_script_import(self):
        run = subprocess.run(
            [sys.executable, 'scripts/report_contract.py', str(self.root)],
            capture_output=True, text=True, check=False,
        )
        self.assertNotIn('ImportError', run.stderr)
        self.assertIn('reports directory is missing', run.stdout)

    def test_valid_official_source_export(self):
        run = self.run_cli()
        self.assertEqual(run.returncode, 0, run.stderr)
        result = json.loads((self.output / "disclosure_candidates.json").read_text(
            encoding="utf-8"))
        self.assertEqual(result["candidates"][0]["provider"], "CNINFO")
        self.assertFalse(result["source_content_verified"])

    def test_lookalike_domain_rejected_without_artifact(self):
        self.record["url"] = "https://static.cninfo.com.cn.evil.example/test.pdf"
        run = self.run_cli()
        self.assertNotEqual(run.returncode, 0)
        self.assertFalse((self.output / "disclosure_candidates.json").exists())

    def test_future_date_rejected_without_artifact(self):
        self.record["announcement_date"] = "2026-11-01"
        run = self.run_cli()
        self.assertNotEqual(run.returncode, 0)
        self.assertFalse((self.output / "disclosure_candidates.json").exists())


if __name__ == "__main__":
    unittest.main()
