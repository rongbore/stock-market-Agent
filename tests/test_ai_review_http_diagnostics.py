import io
import json
import unittest
import urllib.error

from scripts.ai_review_http_client import invoke_review

SHA = "a" * 40

class FakeResponse:
    status = 200
    def __init__(self, content): self.stream = io.BytesIO(content)
    def __enter__(self): return self
    def __exit__(self, *args): return False
    def read(self, n): return self.stream.read(n)

class CaptureOpener:
    def __init__(self, content): self.content=content; self.request=None
    def open(self, request, timeout):
        self.request=request
        return FakeResponse(self.content)

class HttpDiagnosticsTests(unittest.TestCase):
    def test_request_asks_for_json_and_disables_thinking(self):
        content=json.dumps({"choices":[{"message":{"content":'{"verdict":"approve","summary":"ok","findings":[]}'}}]}).encode()
        op=CaptureOpener(content)
        prepared={"head_sha":SHA,"request_digest":"x","request":{"head_sha":SHA,"system_instructions":"json","untrusted_pr_data":"diff"}}
        # use the real digest so preflight succeeds
        from scripts.ai_review_evidence_binding import _digest
        prepared["request_digest"]=_digest(prepared["request"])
        invoke_review(prepared=prepared,expected_head_sha=SHA,expected_digest=prepared["request_digest"],
                      endpoint="https://api.example.com/chat/completions",token="t",model="deepseek-flash",opener=op,allowed_hosts=["api.example.com"])
        body=json.loads(op.request.data)
        self.assertEqual(body["response_format"],{"type":"json_object"})
        self.assertEqual(body["thinking"],{"type":"disabled"})
    def test_http_401_is_sanitized(self):
        class Unauthorized:
            def open(self,*a,**k):
                raise urllib.error.HTTPError("https://api.example.com",401,"unauthorized",{},io.BytesIO(b"secret body"))
        from scripts.ai_review_evidence_binding import _digest
        req={"head_sha":SHA,"system_instructions":"json","untrusted_pr_data":"diff"}
        prepared={"head_sha":SHA,"request":req,"request_digest":_digest(req)}
        with self.assertRaisesRegex(ValueError,"provider_http_401"):
            invoke_review(prepared=prepared,expected_head_sha=SHA,expected_digest=prepared["request_digest"],
                          endpoint="https://api.example.com/chat/completions",token="t",model="deepseek-flash",opener=Unauthorized(),allowed_hosts=["api.example.com"])

if __name__ == "__main__": unittest.main()
