import contextlib
import io
import json
import tempfile
import unittest
from pathlib import Path

from scripts.merge_safety_report import main


class MergeSafetyReportCliTests(unittest.TestCase):
    def run_cli(self, args):
        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            code = main(args)
        return code, json.loads(output.getvalue())

    def test_default_mode_reports_blocker_without_failing(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "input.json"
            path.write_text('{"rulesets": []}', encoding="utf-8")
            code, result = self.run_cli([str(path)])
            self.assertEqual(code, 0)
            self.assertFalse(result["ready"])

    def test_strict_mode_fails_closed(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "input.json"
            path.write_text('{"rulesets": []}', encoding="utf-8")
            code, result = self.run_cli(["--strict", str(path)])
            self.assertEqual(code, 2)
            self.assertEqual(result["decision"], "manual")

    def test_strict_mode_invalid_json_is_blocked(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "invalid.json"
            path.write_text("{", encoding="utf-8")
            code, result = self.run_cli(["--strict", str(path)])
            self.assertEqual(code, 2)
            self.assertTrue(result["blockers"])


if __name__ == "__main__":
    unittest.main()
