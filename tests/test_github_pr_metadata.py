import io
import json
import unittest
from scripts.github_pr_metadata import fetch_pr_metadata

SHA = "a" * 40


class Response:
    def __init__(self, obj):
        self.obj = io.BytesIO(json.dumps(obj).encode())

    def __enter__(self):
        return self.obj

    def __exit__(self, *args):
        self.obj.close()


def pr(sha=SHA, count=1):
    return {"number": 7, "head": {"sha": sha}, "base": {
        "repo": {"full_name": "owner/repo"}}, "draft": False,
        "state": "open", "changed_files": count}


def opener_for(meta, files):
    def opener(req, timeout):
        return Response(files if "/files?" in req.full_url else meta)
    return opener


class GithubPrMetadataTests(unittest.TestCase):
    def test_verified_metadata(self):
        result = fetch_pr_metadata("owner/repo", 7, SHA, token="token",
            opener=opener_for(pr(), [{"filename": "docs/guide.md"}]))
        self.assertEqual(result["changed_paths"], ["docs/guide.md"])
        self.assertFalse(result["merge_authorized"])

    def test_rejects_stale_sha(self):
        with self.assertRaises(ValueError):
            fetch_pr_metadata("owner/repo", 7, SHA, token="token",
                opener=opener_for(pr(sha="b" * 40), [{"filename": "docs/guide.md"}]))

    def test_rejects_incomplete_or_oversized_files(self):
        for count, files in ((2, [{"filename": "docs/a.md"}]),
                             (101, []),
                             (2, [{"filename": "docs/a.md"}, {"filename": "docs/a.md"}])):
            with self.subTest(count=count):
                with self.assertRaises(ValueError):
                    fetch_pr_metadata("owner/repo", 7, SHA, token="token",
                        opener=opener_for(pr(count=count), files))

    def test_rejects_wrong_pr_and_bad_inputs(self):
        for repo, number, token in (("owner/../repo", 7, "token"),
                                    ("owner/repo", 0, "token"),
                                    ("owner/repo", 7, "")):
            with self.assertRaises(ValueError):
                fetch_pr_metadata(repo, number, SHA, token=token)
        meta = pr()
        meta["number"] = 8
        with self.assertRaises(ValueError):
            fetch_pr_metadata("owner/repo", 7, SHA, token="token",
                opener=opener_for(meta, [{"filename": "docs/a.md"}]))


if __name__ == "__main__":
    unittest.main()
