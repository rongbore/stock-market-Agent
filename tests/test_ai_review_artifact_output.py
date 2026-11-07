import json
import os
import tempfile
import unittest

from scripts.ai_review_manual_cli import _write_json_output


class ReviewArtifactTests(unittest.TestCase):
    def test_writes_success_report_as_utf8_json(self):
        payload = {"status": "OK", "summary": "审核通过", "merge_authorized": False}
        with tempfile.TemporaryDirectory() as directory:
            path = os.path.join(directory, "review.json")
            _write_json_output(path, payload)
            with open(path, encoding="utf-8") as source:
                self.assertEqual(json.load(source), payload)

    def test_writes_blocked_report_without_credentials(self):
        payload = {"status": "BLOCKED", "reason": "provider_http_401", "merge_authorized": False}
        with tempfile.TemporaryDirectory() as directory:
            path = os.path.join(directory, "review.json")
            _write_json_output(path, payload)
            with open(path, encoding="utf-8") as source:
                data = json.load(source)
            self.assertEqual(data["reason"], "provider_http_401")
            self.assertNotIn("api_key", data)
            self.assertNotIn("token", data)


if __name__ == "__main__":
    unittest.main()
