import unittest
from scripts.ai_review_envelope import build_envelope

BASE = "a" * 40
HEAD = "b" * 40


def item(path="docs/guide.md", patch="+safe\n"):
    return {"filename": path, "patch": patch, "status": "modified",
            "type": "file", "mode": "100644", "binary": False}


class ReviewEnvelopeTests(unittest.TestCase):
    def test_metadata_only_and_sha_binding(self):
        result = build_envelope([item()], HEAD, BASE)
        self.assertEqual(result["head_sha"], HEAD)
        self.assertEqual(result["file_count"], 1)
        self.assertFalse(result["merge_authorized"])
        self.assertFalse(result["review_complete"])
        self.assertNotIn("patch", result["files"][0])

    def test_reject_unsafe_or_duplicate_files(self):
        for changes in ([item("scripts/run.py")], [item(), item()],
                        [item(patch="x" * 150001)],
                        [dict(item(), binary=True)],
                        [item("docs/../secret.md")]):
            with self.subTest(changes=changes):
                with self.assertRaises(ValueError):
                    build_envelope(changes, HEAD, BASE)


    def test_reject_embedded_secret_or_active_html(self):
        for patch in ('+api_key = "1234567890abcdef"\\n',
                      '+<script>alert(1)</script>\\n'):
            with self.subTest(patch=patch):
                with self.assertRaises(ValueError):
                    build_envelope([item(patch=patch)], HEAD, BASE)

    def test_reject_invalid_sha(self):
        with self.assertRaises(ValueError):
            build_envelope([item()], "main", BASE)


if __name__ == "__main__":
    unittest.main()
