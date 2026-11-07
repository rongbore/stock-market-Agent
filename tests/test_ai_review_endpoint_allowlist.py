import io
import json
import unittest

from scripts.ai_review_evidence_binding import prepare_review
from scripts.ai_review_http_client import invoke_review, _validate_endpoint

SHA = "a" * 40

class Response:
    status = 200
    def __init__(self, body): self.body=io.BytesIO(body)
    def __enter__(self): return self
    def __exit__(self,*a): return False
    def read(self,n): return self.body.read(n)

class Opener:
    def __init__(self, body): self.body=body; self.called=False
    def open(self,request,timeout): self.called=True; return Response(self.body)

class EndpointAllowlistTests(unittest.TestCase):
    def test_exact_allowlisted_host_accepted(self):
        self.assertEqual(_validate_endpoint("https://api.deepseek.com/chat/completions", ["api.deepseek.com"]),
                         "https://api.deepseek.com/chat/completions")

    def test_unlisted_host_rejected(self):
        with self.assertRaisesRegex(ValueError, "not allowlisted"):
            _validate_endpoint("https://attacker.example/chat/completions", ["api.deepseek.com"])

    def test_ip_literal_rejected(self):
        with self.assertRaisesRegex(ValueError, "IP literal"):
            _validate_endpoint("https://127.0.0.1/chat/completions", ["127.0.0.1"])

    def test_query_string_rejected(self):
        with self.assertRaisesRegex(ValueError, "query"):
            _validate_endpoint("https://api.deepseek.com/chat/completions?token=x", ["api.deepseek.com"])

    def test_missing_allowlist_fails_closed(self):
        with self.assertRaisesRegex(ValueError, "allowlist"):
            _validate_endpoint("https://api.deepseek.com/chat/completions", [])

    def test_unlisted_host_never_calls_transport(self):
        p=prepare_review(head_sha=SHA,changed_files=["a.md"],diff="+x")
        op=Opener(json.dumps({"choices":[{"message":{"content":'{"verdict":"approve","summary":"ok","findings":[]}'}}]}).encode())
        with self.assertRaises(ValueError):
            invoke_review(prepared=p,expected_head_sha=SHA,expected_digest=p["request_digest"],
                          endpoint="https://attacker.example/chat/completions",token="t",model="m",
                          opener=op,allowed_hosts=["api.deepseek.com"])
        self.assertFalse(op.called)

if __name__ == "__main__": unittest.main()
