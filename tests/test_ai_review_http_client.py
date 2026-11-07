import io
import json
import unittest

from scripts.ai_review_evidence_binding import prepare_review
from scripts.ai_review_http_client import invoke_review

SHA = "a" * 40
ENDPOINT = "https://api.example.com/v1/chat/completions"


class FakeResponse:
    status = 200

    def __init__(self, content):
        self.stream = io.BytesIO(content)

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def read(self, n):
        return self.stream.read(n)


class FakeOpener:
    def __init__(self, content):
        self.content = content
        self.called = False

    def open(self, request, timeout):
        self.called = True
        assert request.get_method() == "POST"
        return FakeResponse(self.content)


def prepared():
    return prepare_review(head_sha=SHA, changed_files=["docs/guide.md"], diff="+hello")


def invoke(p, opener, **overrides):
    args = dict(prepared=p, expected_head_sha=SHA,
                expected_digest=p["request_digest"], endpoint=ENDPOINT,
                token="fake-token", model="test-model", opener=opener,
                allowed_hosts=["api.example.com"])
    args.update(overrides)
    return invoke_review(**args)


class HttpReviewTests(unittest.TestCase):
    def test_success_remains_untrusted(self):
        content = json.dumps({"verdict": "approve", "summary": "ok", "findings": []})
        envelope = json.dumps({"choices": [{"message": {"content": content}}]}).encode()
        result = invoke(prepared(), FakeOpener(envelope))
        self.assertTrue(result["model_invoked"])
        self.assertFalse(result["merge_authorized"])
        self.assertFalse(result["evidence_authenticated"])

    def test_stale_request_never_calls_network(self):
        p = prepared()
        opener = FakeOpener(b"{}")
        with self.assertRaises(ValueError):
            invoke(p, opener, expected_head_sha="b" * 40)
        self.assertFalse(opener.called)

    def test_http_endpoint_blocked(self):
        with self.assertRaises(ValueError):
            invoke(prepared(), FakeOpener(b"{}"), endpoint="http://example.com")

    def test_missing_token_blocked(self):
        with self.assertRaises(ValueError):
            invoke(prepared(), FakeOpener(b"{}"), token="")

    def test_invalid_json_fails_closed(self):
        with self.assertRaises(ValueError):
            invoke(prepared(), FakeOpener(b"not-json"))

    def test_malformed_provider_payload_fails_closed(self):
        with self.assertRaises(ValueError):
            invoke(prepared(), FakeOpener(b"{}"))


if __name__ == "__main__":
    unittest.main()
