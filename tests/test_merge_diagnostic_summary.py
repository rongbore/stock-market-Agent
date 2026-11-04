import unittest
from scripts.merge_diagnostic_summary import render


class MergeDiagnosticSummaryTests(unittest.TestCase):
    def test_missing_or_invalid_data_is_not_approval(self):
        for payload in (None, {}, {"blockers": []}, {"blockers": "safe"}):
            with self.subTest(payload=payload):
                text = render(payload)
                self.assertIn("Auto-merge remains disabled", text)
                self.assertIn("Diagnostic result unavailable", text)

    def test_blocker_html_and_newlines_are_escaped(self):
        text = render({"blockers": ["<script>bad</script>\nnew line"]})
        self.assertNotIn("<script>", text)
        self.assertIn("&lt;script&gt;", text)
        self.assertIn("new line", text)
        self.assertIn("does not authorize merging", text)


if __name__ == "__main__":
    unittest.main()
