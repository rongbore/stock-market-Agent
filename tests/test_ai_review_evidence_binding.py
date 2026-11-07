import json
import unittest

from scripts.ai_review_evidence_binding import prepare_review, attach_review

SHA = "a" * 40
RESPONSE = json.dumps({"verdict": "approve", "summary": "Looks consistent", "findings": []})


def fixture():
    p = prepare_review(head_sha=SHA, changed_files=["docs/guide.md"], diff="+a")
    return p


class EvidenceBindingTests(unittest.TestCase):
    def test_bound_review_is_not_authorization(self):
        p = fixture()
        r = attach_review(prepared=p, response=RESPONSE,
                          expected_head_sha=SHA, expected_digest=p["request_digest"])
        self.assertEqual(r["status"], "ADVISORY_ONLY")
        self.assertFalse(r["merge_authorized"])
        self.assertFalse(r["evidence_authenticated"])
        self.assertFalse(r["review"]["trusted"])

    def test_changed_diff_blocks(self):
        p = fixture()
        p["request"]["untrusted_pr_data"] += "modified"
        with self.assertRaisesRegex(ValueError, "changed"):
            attach_review(prepared=p, response=RESPONSE, expected_head_sha=SHA,
                          expected_digest=p["request_digest"])

    def test_changed_sha_blocks(self):
        p = fixture()
        with self.assertRaisesRegex(ValueError, "SHA"):
            attach_review(prepared=p, response=RESPONSE, expected_head_sha="b" * 40,
                          expected_digest=p["request_digest"])

    def test_wrong_digest_blocks(self):
        p = fixture()
        with self.assertRaisesRegex(ValueError, "changed"):
            attach_review(prepared=p, response=RESPONSE, expected_head_sha=SHA,
                          expected_digest="0" * 64)

    def test_invalid_model_response_blocks(self):
        p = fixture()
        with self.assertRaises(ValueError):
            attach_review(prepared=p, response="not json", expected_head_sha=SHA,
                          expected_digest=p["request_digest"])

    def test_uncertain_remains_advisory(self):
        p = fixture()
        response = json.dumps({"verdict": "uncertain", "summary": "Missing context", "findings": []})
        r = attach_review(prepared=p, response=response, expected_head_sha=SHA,
                          expected_digest=p["request_digest"])
        self.assertEqual(r["review"]["verdict"], "uncertain")
        self.assertFalse(r["merge_authorized"])


if __name__ == "__main__":
    unittest.main()
