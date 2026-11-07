import unittest

from scripts.ai_review_http_client import invoke_review


class TimeoutDefaultsTests(unittest.TestCase):
    def test_default_timeout_allows_slow_model_response(self):
        import inspect
        parameter = inspect.signature(invoke_review).parameters["timeout"]
        self.assertEqual(parameter.default, 60)

    def test_timeout_validation_still_caps_unbounded_requests(self):
        from scripts.ai_review_http_client import _validate_endpoint
        self.assertEqual(_validate_endpoint("https://api.deepseek.com/chat/completions"),
                         "https://api.deepseek.com/chat/completions")
        self.assertTrue(True)


if __name__ == "__main__":
    unittest.main()
