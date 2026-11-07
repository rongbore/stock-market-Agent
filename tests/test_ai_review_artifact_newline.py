import json
import os
import tempfile
import unittest

from scripts.ai_review_manual_cli import _write_json_output


class ReviewArtifactNewlineTests(unittest.TestCase):
    def test_success_report_is_valid_json_with_terminal_newline(self):
        payload = {"status": "OK", "summary": "审核通过", "merge_authorized": False}
        with tempfile.TemporaryDirectory() as directory:
            path = os.path.join(directory, "review.json")
            _write_json_output(path, payload)
            raw = open(path, encoding="utf-8").read()
            self.assertTrue(raw.endswith("\n"))
            self.assertFalse(raw.endswith("\\n"))
            self.assertEqual(json.loads(raw), payload)

    def test_blocked_report_is_valid_json(self):
        payload = {"status": "BLOCKED", "reason": "provider_http_401", "merge_authorized": False}
        with tempfile.TemporaryDirectory() as directory:
            path = os.path.join(directory, "review.json")
            _write_json_output(path, payload)
            with open(path, encoding="utf-8") as source:
                self.assertEqual(json.load(source), payload)


if __name__ == "__main__":
    unittest.main()
