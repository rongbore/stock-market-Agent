"""Provider exception compatibility without requiring optional AKShare/network."""
import json
from pathlib import Path
import tempfile
import unittest

from scripts.akshare_dual_smoke import _safe_error, run
from tests.test_akshare_dual_smoke import snapshot

RequestConnectionError = type('ConnectionError', (OSError,), {'__module__': 'requests.exceptions'})
RateLimitError = type('RateLimitError', (Exception,), {'__module__': 'akshare.exceptions'})
Push2RateLimitError = type('Push2RateLimitError', (RateLimitError, RequestConnectionError),
                           {'__module__': 'akshare.utils.http'})


class ProviderExceptionDiagnosticsTests(unittest.TestCase):
    def test_rate_limit_precedes_requests_connection_and_never_retries(self):
        for kind in (RateLimitError, Push2RateLimitError):
            calls = []
            waits = []
            def limited(*args):
                calls.append(1)
                raise kind('PRIVATE_RATE_LIMIT_BODY')
            with self.subTest(kind=kind.__name__), tempfile.TemporaryDirectory() as folder:
                result = run('000776.SZ', '2026-10-01', '2026-10-30', folder,
                             eastmoney=limited, sina=lambda *args: snapshot('sina', 'shares', 100),
                             sleep=waits.append)
                raw = (Path(folder) / 'dual_upstream_diagnostics.json').read_text()
                diagnostic = json.loads(raw)
                self.assertEqual(result, 1)
                self.assertEqual(calls, [1])
                self.assertEqual(waits, [])
                self.assertEqual(diagnostic['eastmoney_error_kind'], 'rate_limit')
                self.assertEqual(diagnostic['sina_status'], 'success')
                self.assertNotIn('PRIVATE_RATE_LIMIT_BODY', raw)

    def test_custom_provider_exception_does_not_escape_or_skip_second_source(self):
        for name in ('APIError', 'InvalidParameterError', 'DataParsingError', 'NetworkError'):
            error_type = type(name, (Exception,), {'__module__': 'akshare.exceptions'})
            def fail(*args):
                raise error_type('PRIVATE_PROVIDER_BODY')
            with self.subTest(name=name), tempfile.TemporaryDirectory() as folder:
                run('000776.SZ', '2026-10-01', '2026-10-30', folder,
                    eastmoney=fail, sina=lambda *args: snapshot('sina', 'shares', 100),
                    sleep=lambda _: self.fail('unexpected retry'))
                raw = (Path(folder) / 'dual_upstream_diagnostics.json').read_text()
                diagnostic = json.loads(raw)
                self.assertEqual(diagnostic['eastmoney_attempts'], 1)
                self.assertEqual(diagnostic['sina_status'], 'success')
                self.assertEqual(diagnostic['eastmoney_error_kind'], 'runtime_or_dependency')
                self.assertNotIn('PRIVATE_PROVIDER_BODY', raw)

    def test_unrelated_same_name_is_not_treated_as_provider_rate_limit(self):
        unrelated = type('RateLimitError', (RequestConnectionError,), {'__module__': 'other_provider'})
        self.assertEqual(_safe_error(unrelated()), ('operating_system_or_network', 'request_connection'))

    def test_process_cancellation_propagates_without_fetching_second_source(self):
        for error_type in (KeyboardInterrupt, SystemExit):
            calls = []
            def cancelled(*args):
                raise error_type()
            def second(*args):
                calls.append(1)
                return snapshot('sina', 'shares', 100)
            with self.subTest(error_type=error_type), tempfile.TemporaryDirectory() as folder:
                with self.assertRaises(error_type):
                    run('000776.SZ', '2026-10-01', '2026-10-30', folder,
                        eastmoney=cancelled, sina=second)
                self.assertEqual(calls, [])
